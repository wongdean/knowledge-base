#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest.jsonl"
FTS_DB = ROOT / "indexes" / "kb_fts.db"


def iter_items():
    if not MANIFEST.exists():
        return
    with MANIFEST.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def normalize_url(url: str) -> str:
    p = urllib.parse.urlparse(url.strip())
    scheme = p.scheme or "https"
    netloc = p.netloc.lower()
    path = re.sub(r"/+", "/", p.path or "/")

    q = urllib.parse.parse_qsl(p.query, keep_blank_values=False)
    drop = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "spm", "igshid"}
    q = [(k, v) for k, v in q if k.lower() not in drop]

    # X/Twitter canonicalization: keep status/article ID only
    if "x.com" in netloc or "twitter.com" in netloc:
        m = re.search(r"/(status|article)/(\d+)", path)
        if m:
            path = path[: m.end()]
            q = []

    query = urllib.parse.urlencode(sorted(q)) if q else ""
    return urllib.parse.urlunparse((scheme, netloc, path.rstrip("/"), "", query, ""))


def search(q=None, tag=None):
    q = (q or "").lower()
    for it in iter_items() or []:
        hay = " ".join(
            [
                it.get("title", ""),
                it.get("summary", ""),
                " ".join(it.get("tags", [])),
                it.get("url", ""),
            ]
        ).lower()
        if tag and tag not in it.get("tags", []):
            continue
        if q and q not in hay:
            continue
        print(
            f"- [{it.get('id')}] {it.get('title')}\n"
            f"  url: {it.get('url')}\n"
            f"  tags: {', '.join(it.get('tags', []))}\n"
            f"  path: {it.get('path')}\n"
        )


def _fetch_via_jina(url: str) -> str:
    target = "https://r.jina.ai/http://" + url.replace("https://", "").replace("http://", "")
    req = urllib.request.Request(target, headers={"User-Agent": "kb-bot/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", errors="ignore")


def _read_x_cookie() -> str:
    p = Path.home() / ".config" / "kb" / "x_cookie.txt"
    if p.exists():
        return p.read_text(encoding="utf-8", errors="ignore").strip()
    return ""


def _fetch_x_auth_html(url: str) -> str:
    cookie = _read_x_cookie()
    if not cookie:
        return ""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Cookie": cookie,
            "Referer": "https://x.com/",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="ignore")


def _guess_source(url: str) -> str:
    netloc = urllib.parse.urlparse(url).netloc.lower()
    if "x.com" in netloc or "twitter.com" in netloc:
        return "x"
    return "web"


def _extract_title(text: str, fallback: str) -> str:
    m = re.search(r"^Title:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else fallback


def _extract_body(text: str) -> str:
    m = re.search(r"Markdown Content:\n(.*)$", text, re.DOTALL)
    return (m.group(1).strip() if m else text.strip())


def _extract_x_image_urls(raw: str, body: str):
    urls = []

    # direct pbs.twimg links
    for u in re.findall(r"https://pbs\.twimg\.com/media/[^\s\)\]]+", raw + "\n" + body):
        u = u.strip()
        if u not in urls:
            urls.append(u)

    # x.com/.../media/<id> links -> construct pbs link
    for media_id in re.findall(r"/media/(\d+)", raw + "\n" + body):
        cand = f"https://pbs.twimg.com/media/{media_id}?format=jpg&name=orig"
        if cand not in urls:
            urls.append(cand)

    return urls


def _download_assets(image_urls, assets_dir: Path):
    assets_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    seen_keys = set()

    for i, u in enumerate(image_urls, 1):
        base = u.split("?")[0]
        ext = "jpg"
        m = re.search(r"format=([a-zA-Z0-9]+)", u)
        if m:
            ext = m.group(1).lower()

        attempts = [f"{base}?format={ext}&name=orig", u]
        if ext != "jpg":
            attempts.append(f"{base}?format=jpg&name=orig")

        data = None
        used = None
        ctype = ""
        for a in attempts:
            try:
                req = urllib.request.Request(a, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://x.com/"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                    ctype = (r.headers.get("Content-Type") or "").lower()
                if data and len(data) > 500:
                    used = a
                    break
            except Exception:
                continue

        if not data or not used:
            continue

        real_ext = "jpg"
        if "png" in ctype:
            real_ext = "png"
        elif "webp" in ctype:
            real_ext = "webp"

        key = (len(data), real_ext)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        name = Path(base).name
        fn = f"{name}.{real_ext}" if name else f"img_{i}.{real_ext}"
        path = assets_dir / fn
        path.write_bytes(data)
        saved.append({"file": f"assets/{fn}", "source": used, "bytes": len(data), "content_type": ctype})

    return saved


def _summarize(body: str, max_len: int = 320) -> str:
    clean = re.sub(r"\s+", " ", body)
    parts = re.split(r"(?<=[。！？.!?])\s+", clean)
    summary = " ".join(parts[:3]).strip()
    return (summary[: max_len - 1] + "…") if len(summary) > max_len else summary


def _auto_tags(title: str, body: str, source: str):
    text = f"{title}\n{body}".lower()
    tags = []

    def add(t):
        if t not in tags:
            tags.append(t)

    if source == "x":
        add("X")
    if "openclaw" in text:
        add("OpenClaw")
    if any(k in text for k in ["agent", "编排", "workflow", "自动化"]):
        add("Agent编排")
    if any(k in text for k in ["变现", "赚钱", "收入", "报价", "客户", "接单"]):
        add("AI变现")
    if any(k in text for k in ["小红书", "获客", "增长", "咨询"]):
        add("内容获客")
    if any(k in text for k in ["复盘", "总结", "经验"]):
        add("案例复盘")
    if any(k in text for k in ["all in", "特斯拉", "夸张", "爆赚"]):
        add("高风险宣传")

    return tags or ["待分类"]


def _slug(s: str, n: int = 48):
    s = s.lower()
    s = re.sub(r"https?://", "", s)
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", s)
    s = s.strip("-")
    return s[:n] if s else "entry"


def _load_manifest_state():
    ids, urls = set(), set()
    for it in iter_items() or []:
        if it.get("id"):
            ids.add(it["id"])
        if it.get("normalized_url"):
            urls.add(it["normalized_url"])
        elif it.get("url"):
            urls.add(normalize_url(it["url"]))
    return ids, urls


def add_url(url: str, tags_arg: str = "", title_arg: str = ""):
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    source = _guess_source(url)
    nurl = normalize_url(url)

    ids, urls = _load_manifest_state()
    h = hashlib.sha1(nurl.encode("utf-8")).hexdigest()[:12]
    item_id = f"{source}-{h}"

    if item_id in ids:
        print(f"already exists: {item_id}")
        return False
    if nurl in urls:
        print(f"already exists by URL: {nurl}")
        return False

    raw = _fetch_via_jina(nurl)
    auth_html = ""
    if source == "x":
        try:
            auth_html = _fetch_x_auth_html(nurl)
        except Exception:
            auth_html = ""

    body = _extract_body(raw)
    title = title_arg.strip() or _extract_title(raw, fallback=nurl)
    summary = _summarize(body)

    auto_tags = _auto_tags(title, body, source)
    manual_tags = [t.strip() for t in tags_arg.split(",") if t.strip()]
    tags = []
    for t in auto_tags + manual_tags:
        if t not in tags:
            tags.append(t)

    day = now.strftime("%Y-%m-%d")
    dir_name = f"{day}-{_slug(title)}-{h}"
    entry_dir = ROOT / "sources" / source / dir_name
    entry_dir.mkdir(parents=True, exist_ok=True)

    image_section = ""
    image_meta = {"images": []}
    if source == "x":
        image_urls = _extract_x_image_urls(raw, body)
        saved = _download_assets(image_urls, entry_dir / "assets")
        if saved:
            image_meta = {"images": saved}
            lines = ["## Images (archived)", ""] + [f"![]({s['file']})\n" for s in saved]
            image_section = "\n" + "\n".join(lines)

    (entry_dir / "article.md").write_text(
        f"# {title}\n\n"
        f"- Source: {nurl}\n"
        f"- Captured at: {now.isoformat()}\n\n"
        f"## Content\n\n{body}\n"
        f"{image_section}",
        encoding="utf-8",
    )
    (entry_dir / "raw.txt").write_text(raw, encoding="utf-8")
    if auth_html:
        (entry_dir / "raw-auth.html").write_text(auth_html, encoding="utf-8")
    (entry_dir / "meta-images.json").write_text(json.dumps(image_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (entry_dir / "summary.md").write_text(f"# 摘要\n\n{summary}\n", encoding="utf-8")
    (entry_dir / "tags.json").write_text(
        json.dumps({"url": nurl, "title": title, "tags": tags, "source": source}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    rec = {
        "id": item_id,
        "source": source,
        "title": title,
        "url": nurl,
        "normalized_url": nurl,
        "captured_at": now.isoformat(),
        "tags": tags,
        "summary": summary,
        "path": str((Path("sources") / source / dir_name / "article.md").as_posix()),
    }
    with MANIFEST.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"added: {item_id}")
    print(f"path: {entry_dir}")
    print(f"tags: {', '.join(tags)}")
    if source == "x":
        print(f"images: {len(image_meta.get('images', []))}")
    return True


def add_from_file(file_path: str, tags_arg: str = ""):
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(file_path)
    urls = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)

    ok, skip, fail = 0, 0, 0
    for u in urls:
        try:
            created = add_url(u, tags_arg=tags_arg)
            if created:
                ok += 1
            else:
                skip += 1
        except Exception as e:
            fail += 1
            print(f"failed: {u} -> {e}")

    print(f"batch done: added={ok}, skipped={skip}, failed={fail}")


def rebuild_fts():
    FTS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(FTS_DB)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS docs")
    cur.execute("CREATE VIRTUAL TABLE docs USING fts5(id, title, summary, tags, url, path, content)")

    count = 0
    for it in iter_items() or []:
        content = ""
        rel = it.get("path")
        if rel:
            p = ROOT / rel
            if p.exists():
                content = p.read_text(encoding="utf-8", errors="ignore")
        cur.execute(
            "INSERT INTO docs(id, title, summary, tags, url, path, content) VALUES(?,?,?,?,?,?,?)",
            (
                it.get("id", ""),
                it.get("title", ""),
                it.get("summary", ""),
                " ".join(it.get("tags", [])),
                it.get("url", ""),
                it.get("path", ""),
                content,
            ),
        )
        count += 1

    conn.commit()
    conn.close()
    print(f"fts rebuilt: {count} docs -> {FTS_DB}")


def search_fts(query: str, limit: int = 20):
    if not FTS_DB.exists():
        print("fts db not found, run: python3 scripts/kb.py rebuild-fts")
        return
    conn = sqlite3.connect(FTS_DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, url, tags, path FROM docs WHERE docs MATCH ? LIMIT ?",
        (query, limit),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("no results")
        return

    for r in rows:
        print(f"- [{r[0]}] {r[1]}\n  url: {r[2]}\n  tags: {r[3]}\n  path: {r[4]}\n")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="Search manifest")
    s.add_argument("query", nargs="?", default="")
    s.add_argument("--tag", default="")

    a = sub.add_parser("add", help="Add URL into KB")
    a.add_argument("url")
    a.add_argument("--tags", default="", help="extra tags, comma-separated")
    a.add_argument("--title", default="", help="override title")

    b = sub.add_parser("add-batch", help="Add URLs from file (one URL per line)")
    b.add_argument("file")
    b.add_argument("--tags", default="", help="extra tags for all URLs")

    rf = sub.add_parser("rebuild-fts", help="Build/rebuild SQLite FTS index")

    sf = sub.add_parser("search-fts", help="Full-text search via SQLite FTS5")
    sf.add_argument("query")
    sf.add_argument("--limit", type=int, default=20)

    args = p.parse_args()
    if args.cmd == "search":
        search(args.query, args.tag or None)
    elif args.cmd == "add":
        add_url(args.url, tags_arg=args.tags, title_arg=args.title)
    elif args.cmd == "add-batch":
        add_from_file(args.file, tags_arg=args.tags)
    elif args.cmd == "rebuild-fts":
        rebuild_fts()
    elif args.cmd == "search-fts":
        search_fts(args.query, args.limit)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
