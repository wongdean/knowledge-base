#!/usr/bin/env bash
set -euo pipefail

KB_DIR="/home/coco/.openclaw/workspace/knowledge-base"
WS_DIR="/home/coco/.openclaw/workspace"
OC_DIR="/home/coco/.openclaw"
DATE_TAG="$(date +%F)"
TIME_TAG="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="$KB_DIR/backups/openclaw-config/nightly/$DATE_TAG"
mkdir -p "$OUT_DIR"

copy_if_exists() {
  local src="$1" dst="$2"
  if [[ -e "$src" ]]; then
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
  fi
}

# 1) core workspace files
for f in AGENTS.md SOUL.md TOOLS.md IDENTITY.md USER.md HEARTBEAT.md MEMORY.md; do
  [[ -f "$WS_DIR/$f" ]] && cp -f "$WS_DIR/$f" "$OUT_DIR/$f"
done

# 2) skills
[[ -d "$WS_DIR/skills" ]] && { mkdir -p "$OUT_DIR/workspace-skills"; cp -a "$WS_DIR/skills/." "$OUT_DIR/workspace-skills/"; }
[[ -d "$OC_DIR/skills" ]] && { mkdir -p "$OUT_DIR/user-skills"; cp -a "$OC_DIR/skills/." "$OUT_DIR/user-skills/"; }

# 3) crontab backups
shopt -s nullglob
for c in "$OC_DIR"/crontab.backup*; do cp -f "$c" "$OUT_DIR/"; done
shopt -u nullglob

# 4) redact and save openclaw.json + memory files
python3 - << 'PY'
import json, pathlib, re, hashlib, os
WS=pathlib.Path('/home/coco/.openclaw/workspace')
OC=pathlib.Path('/home/coco/.openclaw')
OUT=pathlib.Path(os.environ['OUT_DIR'])

sensitive_keys={'token','bottoken','apikey','auth_token','ct0','cookie','password','secret'}

def redact_obj(obj):
    if isinstance(obj, dict):
        out={}
        for k,v in obj.items():
            kl=k.lower()
            if any(sk in kl for sk in sensitive_keys):
                out[k]='<REDACTED>'
            else:
                out[k]=redact_obj(v)
        return out
    if isinstance(obj, list):
        return [redact_obj(x) for x in obj]
    return obj

cfg=OC/'openclaw.json'
if cfg.exists():
    data=json.loads(cfg.read_text())
    (OUT/'openclaw.json.redacted').write_text(json.dumps(redact_obj(data),ensure_ascii=False,indent=2)+'\n')

# text redaction for memory-like files
patterns=[
    (re.compile(r'(?i)(auth_token\s*[=:]\s*)([^\s;]+)'), r'\1<REDACTED>'),
    (re.compile(r'(?i)(ct0\s*[=:]\s*)([^\s;]+)'), r'\1<REDACTED>'),
    (re.compile(r'(?i)(api[_-]?key\s*[=:]\s*)([^\s;]+)'), r'\1<REDACTED>'),
    (re.compile(r'(?i)(bot[_-]?token\s*[=:]\s*)([^\s;]+)'), r'\1<REDACTED>'),
    (re.compile(r'(?i)(cookie\s*[=:]\s*)([^\n]+)'), r'\1<REDACTED>'),
    (re.compile(r'gh[pousr]_[A-Za-z0-9_]{20,}'), '<REDACTED_GITHUB_TOKEN>'),
]

def redact_text(s:str)->str:
    t=s
    for p,r in patterns:
        t=p.sub(r,t)
    return t

mem_sources=[]
if (WS/'memory').exists(): mem_sources.append((WS/'memory','workspace-memory'))
if (OC/'memory').exists(): mem_sources.append((OC/'memory','openclaw-memory'))
if (WS/'MEMORY.md').exists():
    mem_sources.append((WS/'MEMORY.md','MEMORY.md'))

manifest=[]
for src,name in mem_sources:
    if src.is_dir():
        for p in src.rglob('*'):
            if p.is_file():
                # only keep text-like memory artifacts for public backup
                if p.suffix.lower() not in {'.md','.txt','.json','.jsonl','.yaml','.yml','.log'}:
                    continue
                rel=p.relative_to(src)
                outp=OUT/name/rel
                outp.parent.mkdir(parents=True,exist_ok=True)
                txt=p.read_text(errors='ignore')
                red=redact_text(txt)
                outp.write_text(red)
                manifest.append({'file':f'{name}/{rel.as_posix()}','sha256':hashlib.sha256(red.encode()).hexdigest()})
    else:
        txt=src.read_text(errors='ignore')
        red=redact_text(txt)
        outp=OUT/name
        outp.parent.mkdir(parents=True,exist_ok=True)
        outp.write_text(red)
        manifest.append({'file':name,'sha256':hashlib.sha256(red.encode()).hexdigest()})

(OUT/'memory-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
PY

# 5) snapshot README
cat > "$OUT_DIR/README.md" <<TXT
# Nightly OpenClaw Backup Snapshot

- Date: $DATE_TAG
- Generated at: $TIME_TAG
- Mode: redacted-for-github

Includes:
- Workspace core files + skills
- Redacted openclaw config
- Redacted memory-like files (workspace/openclaw memory)
- Crontab backup files

Notes:
- Secrets are intentionally removed/redacted.
- For restore, run:
  bash scripts/restore-openclaw-config.sh backups/openclaw-config/20260315_232439
TXT

# 6) commit and push if changed
cd "$KB_DIR"
git add "backups/openclaw-config/nightly/$DATE_TAG"
if ! git diff --cached --quiet; then
  git commit -m "backup(nightly): openclaw config snapshot $DATE_TAG"
  git push origin master
fi
