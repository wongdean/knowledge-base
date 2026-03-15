# OpenClaw 配置恢复 Runbook（无密钥版）

> 目标：在新机器/重装后，**快速恢复可公开备份的 OpenClaw 配置**，并把密钥手动补回。

## 0) 前提

- 已安装 OpenClaw
- 已 clone 本仓库
- 有本机用户目录写权限

## 1) 执行恢复脚本

```bash
bash scripts/restore-openclaw-config.sh backups/openclaw-config/20260315_232439
```

脚本会：
- 恢复 workspace 的核心配置文件（AGENTS/SOUL/TOOLS/IDENTITY/USER/HEARTBEAT）
- 恢复用户技能目录和 workspace 技能目录
- 复制 crontab 备份文件到 `~/.openclaw/`
- 将脱敏配置写入 `~/.openclaw/openclaw.json.redacted.from-backup`

## 2) 手动补密钥（必须）

脚本不会恢复任何 token/cookie/apiKey。请手动配置：

- Telegram bot token
- Gateway auth token
- Tavily API key
- 其他插件 API key
- X cookie（本地私有文件）

建议把敏感项放在：
- `~/.config/kb/x_cookie.txt`（仅本机可读）

## 3) 验证

```bash
openclaw status
openclaw gateway status
```

然后做一次最小链路测试：
- 在目标群里 @bot 发一句测试消息
- 如果需要文章抓取，测试一次抓取 -> 入库 -> push

## 4) 故障排查

- 若技能未生效：重启 gateway
  ```bash
  openclaw gateway restart
  ```
- 若配置冲突：对比以下文件手工合并
  - `~/.openclaw/openclaw.json`
  - `~/.openclaw/openclaw.json.redacted.from-backup`

## 5) 安全说明

- 本方案故意不备份 secrets，避免仓库泄漏时造成接管风险。
- 恢复后建议立即轮换关键 token（尤其是历史曾暴露过的）。
