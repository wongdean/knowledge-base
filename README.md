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
python3 scripts/kb.py search "OpenClaw"
python3 scripts/kb.py search --tag "Agent编排"
```
