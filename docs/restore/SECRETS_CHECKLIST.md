# Secrets Checklist（恢复后必填）

> 这份清单用于恢复后人工补齐密钥。不要把真实值写进仓库。

## OpenClaw 核心

- [ ] `channels.telegram.botToken`
- [ ] `gateway.auth.token`
- [ ] `skills.entries.tavily-search.apiKey`（如启用）
- [ ] `plugins.entries.*.config.apiKey`（按实际插件）

## 本地私有文件

- [ ] `~/.config/kb/x_cookie.txt`（仅本机保存，不上传）

## 验证步骤

```bash
openclaw status
openclaw gateway status
```

- [ ] 群里 @bot 测试一次
- [ ] 跑一次文章抓取 -> 入库 -> push 全链路
