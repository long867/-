# 新增资讯与矿眸智探

矿眸智探查询已发布文章的原文证据。导入新文章时同步保存 `article_chunks`，
因此无需重新训练模型，新资料提交后即可用于问答。前端导航、咨询入口、问答页
和后端身份回答统一使用“矿眸智探”。

## 历史资讯采集

RSS 历史翻页必须显式配置，普通定时采集仍只读取最近一页：

```yaml
parser_config:
  fetch_full_content: false
  max_items: 600
  pagination:
    mode: page
    param: paged
    start: 1
    max_pages: 50
```

采集器遵守 robots.txt、域名访问间隔和响应大小限制。重复页面、空页面或
404/410 会终止翻页；后续页面失败时保留已采集内容，并记录失败，避免推进
失败批次的增量检查点。需要授权的正文不得通过历史采集绕过权限，公开 RSS
摘要与完整正文在原始记录中保留各自的实际内容。

## 加工与导入

`pipeline/processors/backfill.py` 对每条独立资料生成中文标题、100–200 字摘要
及实体标签。数字与单位占位符在一个批次中保持唯一，防止不同文章互相混用。
标题校验完整数字，摘要校验原文数值、币种和单位；没有原文依据的标签不会
补齐。未翻译的英文正文保留在 `content`，`content_zh` 为 NULL，
`is_translated` 为 false。

审核后 JSONL 每行包含 `source`、`article`、`enriched` 三个对象。
导入命令再次校验数值、单位、矿种和地区，并逐篇事务写入：

```powershell
# 在项目根目录运行；使用已经配置的 PostgreSQL 和 Redis。
. .\scripts\use_d_drive.ps1
.\.venv\Scripts\python.exe -m pipeline.import_backfill reviewed.jsonl --publish
```

没有 `--publish` 时以 processed 状态保存，不对公众或问答检索开放。
URL 规范化、唯一约束和原文指纹保证重复导入不新增副本。原文证据块使用
精确字符起止位置，中文标题与摘要加入检索字段；每 25 条和完成时刷新公开
缓存。历史导入不会把归档翻页参数写入现有定时采集配置。

## 小服务器的问答检索

2GB 部署采用 `ML_ENABLED=false`：使用 PostgreSQL 全文检索及中英矿种别名
扩展，不在服务器加载 BGE，也不写伪造的向量。问答从新旧已发布语料中检索
原文，校验模型回答的引用片段和数值；引用包含原文链接、来源、日期及位置。
开启真实向量模型后，可在完成正文翻译的文章上运行现有增量索引任务。

新增集成测试验证了导入幂等性、证据切片与原文一致、新资料立即可检索，
以及不存在于原文的数字被拒绝；身份测试验证了“你叫什么名字”的回答为
矿眸智探，并且不会调用模型或占用资讯引用。

## 全球初始化与持续更新

公开 RSS/Atom 信源增加了 International Mining、Engineering & Mining Journal、
African Mining Market、Mining Zimbabwe、Rumbo Minero、Portal da Mineração 和
加拿大自然资源部官方动态。矿业新闻每 6 小时检查一次，现货价格每 24 小时检查。
需要授权的信源保持关闭；暂时不可访问的公开信源记录失败并退避重试。

小服务器使用 `ENRICHMENT_MODE=editorial`，对原文生成中文标题和 100–200 字摘要，
校验数值与单位，保留原文正文和准确证据位置。`AUTO_PUBLISH=true` 后，
正常增量采集按 `PUBLISH_QUALITY_THRESHOLD` 发布；明确初始化的历史资料使用
`INITIALIZATION_QUALITY_THRESHOLD`，避免时效分下降直接排除有用的历史原文。
两个流程都必须通过事实校验和矿产主题检查；历史发布日期不会修改成采集时间。
币种校验同时识别英镑、欧元的符号和中文名称，拒绝把股份数量误写为金额。

初始化原文通过 `python -m pipeline.seed_archive seed-originals.jsonl` 入库为 pending。
Celery 每 15 分钟恢复至多 100 篇，单并发加工，任务失败重试最多 3 次。
失败资料保留错误记录，不直接进入公开问答。服务器重启后继续处理未完成队列，
无需保持本机电脑在线。已校验的检查点可使用 `pipeline.import_backfill --publish`
导入，并立即生成可检索的原文片段。

离线批量加工支持断点续跑和信源交替选样：

```powershell
python -m pipeline.bootstrap --input-dir artifacts/global-bootstrap-20261012 `
  --output-dir artifacts/global-bootstrap-20261012 --limit 1500 --batch-size 4
```

中文标题和摘要已完成时，英文正文的 `is_translated` 仍为 false。
自动发布不会把未翻译正文标记成已翻译，也不会创建替代真实语义向量的伪向量。
