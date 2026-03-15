#!/usr/bin/env bash
set -euo pipefail

KB_DIR="/home/coco/.openclaw/workspace/knowledge-base"
DATE_TAG="$(date +%F)"
TIME_TAG="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="$KB_DIR/backups/openclaw-config/secure/$DATE_TAG"
TMP_DIR="/tmp/openclaw/secure-backup-$TIME_TAG"
PASS_FILE="${BACKUP_PASSPHRASE_FILE:-$HOME/.config/kb/backup_passphrase}"

mkdir -p "$OUT_DIR" "$TMP_DIR"
cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

if [[ ! -f "$PASS_FILE" ]]; then
  echo "[ERR] passphrase file not found: $PASS_FILE"
  echo "Create it first (600 perms), then rerun."
  exit 2
fi

# Gather sensitive-but-needed restore artifacts (local temp only)
mkdir -p "$TMP_DIR/home/.openclaw" "$TMP_DIR/home/.config/kb"

copy_if_exists() {
  local src="$1" dst="$2"
  if [[ -e "$src" ]]; then
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
  fi
}

copy_if_exists "$HOME/.openclaw/openclaw.json" "$TMP_DIR/home/.openclaw/openclaw.json"
copy_if_exists "$HOME/.openclaw/memory" "$TMP_DIR/home/.openclaw/memory"
copy_if_exists "$HOME/.config/kb/x_cookie.txt" "$TMP_DIR/home/.config/kb/x_cookie.txt"

# pack + encrypt
ARCHIVE_BASENAME="openclaw-secure-$TIME_TAG"
TAR_PATH="$OUT_DIR/$ARCHIVE_BASENAME.tar.gz"
ENC_PATH="$TAR_PATH.enc"

( cd "$TMP_DIR" && tar -czf "$TAR_PATH" . )
openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
  -in "$TAR_PATH" -out "$ENC_PATH" -pass "file:$PASS_FILE"
rm -f "$TAR_PATH"

# metadata only (safe)
cat > "$OUT_DIR/$ARCHIVE_BASENAME.meta.json" <<JSON
{
  "createdAt": "$TIME_TAG",
  "format": "tar.gz + openssl aes-256-cbc pbkdf2",
  "encryptedFile": "$(basename "$ENC_PATH")",
  "notes": "Contains sensitive restore artifacts. Keep passphrase private."
}
JSON

# commit and push encrypted artifact
cd "$KB_DIR"
git add "backups/openclaw-config/secure/$DATE_TAG"
if ! git diff --cached --quiet; then
  git commit -m "backup(secure): encrypted OpenClaw snapshot $TIME_TAG"
  git push origin master
fi

echo "[OK] secure encrypted backup pushed: $ENC_PATH"
