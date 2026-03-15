# OpenClaw Config Backup

Created at: 2026-03-15T23:24:39.793823

Included:
- Core workspace persona/config markdown files
- Redacted ~/.openclaw/openclaw.json (secrets removed)
- OpenClaw crontab backups
- workspace skills and user skills directories

Excluded on purpose:
- Any raw tokens/cookies/auth secrets
- Logs, delivery queue, memory cache, runtime state

Restore tip:
- Merge files manually; do not overwrite secrets blindly.
