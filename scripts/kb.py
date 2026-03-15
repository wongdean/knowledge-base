#!/usr/bin/env python3
import argparse, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest.jsonl"

def iter_items():
    if not MANIFEST.exists():
        return
    with MANIFEST.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

def search(q=None, tag=None):
    q = (q or "").lower()
    for it in iter_items() or []:
        hay = " ".join([
            it.get("title", ""),
            it.get("summary", ""),
            " ".join(it.get("tags", [])),
            it.get("url", ""),
        ]).lower()
        if tag and tag not in it.get("tags", []):
            continue
        if q and q not in hay:
            continue
        print(f"- [{it.get('id')}] {it.get('title')}\n  url: {it.get('url')}\n  tags: {', '.join(it.get('tags', []))}\n  path: {it.get('path')}\n")

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search")
    s.add_argument("query", nargs="?", default="")
    s.add_argument("--tag", default="")

    args = p.parse_args()
    if args.cmd == "search":
        search(args.query, args.tag or None)

if __name__ == "__main__":
    main()
