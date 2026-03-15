#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup-dir>"
  echo "Example: $0 backups/openclaw-config/20260315_232439"
  exit 1
fi

BACKUP_DIR="$1"
if [[ ! -d "$BACKUP_DIR" ]]; then
  echo "[ERR] backup dir not found: $BACKUP_DIR"
  exit 1
fi

HOME_DIR="${HOME}"
WS_DIR="$HOME_DIR/.openclaw/workspace"
OC_DIR="$HOME_DIR/.openclaw"
STAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$WS_DIR" "$OC_DIR" "$OC_DIR/skills"

echo "[1/5] restore workspace core files"
for f in AGENTS.md SOUL.md TOOLS.md IDENTITY.md USER.md HEARTBEAT.md; do
  if [[ -f "$BACKUP_DIR/$f" ]]; then
    if [[ -f "$WS_DIR/$f" ]]; then
      cp -f "$WS_DIR/$f" "$WS_DIR/$f.bak.$STAMP"
    fi
    cp -f "$BACKUP_DIR/$f" "$WS_DIR/$f"
    echo "  - restored $f"
  fi
done

echo "[2/5] restore user skills"
if [[ -d "$BACKUP_DIR/user-skills" ]]; then
  cp -a "$BACKUP_DIR/user-skills/." "$OC_DIR/skills/"
  echo "  - restored ~/.openclaw/skills"
fi

echo "[3/5] restore workspace skills"
if [[ -d "$BACKUP_DIR/workspace-skills" ]]; then
  mkdir -p "$WS_DIR/skills"
  cp -a "$BACKUP_DIR/workspace-skills/." "$WS_DIR/skills/"
  echo "  - restored ~/.openclaw/workspace/skills"
fi

echo "[4/5] restore crontab backup files"
shopt -s nullglob
for c in "$BACKUP_DIR"/crontab.backup*; do
  cp -f "$c" "$OC_DIR/"
  echo "  - copied $(basename "$c")"
done
shopt -u nullglob

echo "[5/5] place redacted config for manual merge"
if [[ -f "$BACKUP_DIR/openclaw.json.redacted" ]]; then
  cp -f "$BACKUP_DIR/openclaw.json.redacted" "$OC_DIR/openclaw.json.redacted.from-backup"
  echo "  - wrote ~/.openclaw/openclaw.json.redacted.from-backup"
fi

cat <<MSG

Done.
Next required manual steps:
1) Fill secrets manually (token/cookie/apiKey)
2) Validate with: openclaw status && openclaw gateway status
3) Restart if needed: openclaw gateway restart

MSG
