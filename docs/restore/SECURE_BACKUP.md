# OpenClaw 加密备份（密码解密）

这层是给“尽量平迁”准备的：
- 备份 `~/.openclaw/openclaw.json`（含真实密钥）
- 备份 `~/.openclaw/memory/`（含 sqlite）
- 备份 `~/.config/kb/x_cookie.txt`

全部打包后使用 **AES-256 + PBKDF2** 加密，再推送到 GitHub（仓库里只有密文）。

---

## 1) 初始化密码文件（本机一次）

```bash
mkdir -p ~/.config/kb
umask 077
read -rsp "Set backup passphrase: " P; echo
printf "%s" "$P" > ~/.config/kb/backup_passphrase
unset P
chmod 600 ~/.config/kb/backup_passphrase
```

> 不要把这个文件上传到任何仓库。

## 2) 手动执行一次加密备份

```bash
bash scripts/nightly-openclaw-secure-backup.sh
```

输出位置：
- `backups/openclaw-config/secure/YYYY-MM-DD/*.tar.gz.enc`

## 3) 恢复（在新机器）

1. 准备同样的密码文件 `~/.config/kb/backup_passphrase`
2. 解密：

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -in openclaw-secure-XXXXXXXX_XXXXXX.tar.gz.enc \
  -out openclaw-secure.tar.gz \
  -pass file:$HOME/.config/kb/backup_passphrase
```

3. 解包并按目录覆盖到 `$HOME/`

```bash
tar -xzf openclaw-secure.tar.gz
# 会得到 home/.openclaw 和 home/.config/kb
cp -a home/. "$HOME/"
```

4. 重启并验证

```bash
openclaw gateway restart
openclaw status
```

## 4) 定时任务建议

你现在已有 03:00 的脱敏备份。建议加一个 03:20 的加密备份，避免并发冲突。
