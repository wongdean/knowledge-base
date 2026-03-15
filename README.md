# knowledge-base

长期知识库（单仓库），用于：
1) 文章归档（防删文）
2) 本地检索（离线可查）
3) 作为 Agent 背景材料

## 结构
- `sources/x/`：X 文章归档
- `sources/web/`：通用网页归档
- `notes/`：人工摘要/观点
- `tags/taxonomy.yaml`：标签词表
- `manifest.jsonl`：每篇一条元数据
- `scripts/kb.py`：入库/检索脚本

## 快速用法
```bash
# 入库（自动抓取 + 自动摘要 + 自动标签）
python3 scripts/kb.py add "https://x.com/xxx/status/123"

# 批量入库（txt 每行一个 URL，# 开头为注释）
python3 scripts/kb.py add-batch urls.txt

# 可追加你自己的标签
python3 scripts/kb.py add "https://example.com/article" --tags "行业洞察,竞品"

# 轻量检索（基于 manifest）
python3 scripts/kb.py search "OpenClaw"
python3 scripts/kb.py search --tag "Agent编排"

# 全文检索（SQLite FTS）
python3 scripts/kb.py rebuild-fts
python3 scripts/kb.py search-fts "OpenClaw AND Agent"
```

## 特性
- URL 规范化与去重（避免同文重复入库）
- 单仓库持续追加，不再一文一仓
- 可离线全文检索（FTS 索引建立后）
