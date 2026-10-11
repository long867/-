# 阶段 1 验证记录

日期：2026-10-10，Asia/Shanghai。测试记录与真实采集统计保存在 [phase1-evidence.json](phase1-evidence.json)。

## 已执行并通过

- **70 项后端测试全部通过**，包括 10 项数据库集成测试。覆盖 URL 和近似转载去重、不同事实报道保留、摘要升级正文、采集统计、304、部分批次不提交游标、API 分页恢复、跨域分页拒绝、缺失原文链接拒绝、429 重试与 403 不重试、认证头隔离、robots 禁止、gzip 单次解压、公网地址固定、DoH 私网答案拒绝、Yahoo 期货单位/日期、SEC 表单过滤、翻译失败、数字一致性、原文分块、完整英文加工和管理员重新加工。
- Ruff `check` 与 `format --check` 均通过，共 68 个 Python 文件。`scripts/browser_smoke.py` 通过 E501 检查，行长限制 88。
- 数据库在线执行 `0001_initial → 0002_collection`，`alembic check` 返回 **No new upgrade operations detected**。完整升级 SQL 和阶段 1 降级 SQL均成功生成。
- Next.js `npm run typecheck` 与 `npm run build` 通过。后台采集统计改为分别显示采集、新增、重复、错误，已加工文章可重新加工；已发布文章须先撤回。
- 38 条 YAML 信源配置及全部监控 JSON/YAML 可解析；OpenAPI 和数据库 SQL 文档已更新。

## 真实采集和入库

在本机网络中，系统 DNS 返回代理使用的 `198.18.x.x` 地址。保持私网/保留地址拒绝策略，通过显式配置 DoH 和连接到已校验公网 IP 完成测试。

实测可采集：Mining Weekly RSS、Mining Technology RSS、Resource World RSS、USGS 经过文章路径约束的新闻列表和正文。目录默认仅启用这 4 条。Mining.com / Australian Mining 当前返回 403，Cobalt Institute 返回空 Feed，部分中文入口出现连接超时或安全校验失败，均保留关闭状态。未将错误页、首页或空 Feed 当作有效新闻。

Resource World 实际结果：

- 首次采集 10 篇，新增 10 篇，错误 0。
- 再次运行收到 HTTP 304，新增 0，错误 0；已有 URL 不重复插入。
- 数据库实际有 10 篇对应文章，全部处于 processed 状态；10 篇的 minerals、regions、companies 均非空。
- 生成 120 个保留原文位置的证据分块，并为 10 篇文章建立事件关联。
- 本机未配置真实 LLM：10 篇外文文章的完整翻译数为 0。已明确记录规则模式，没有冒充译文，也没有自动发布这些文章。

英文 `title_zh / summary_zh / content_zh` 落库、100–200 字摘要、实体筛选和事件关系，已通过**明确标注的 LLM 测试响应**验证。该测试证明加工和存储流程，不代表真实模型翻译质量已完成验收。使用真实模型后的验收命令见 [采集说明](phase1-collection.md)。

## 数据库环境边界

本机没有 Docker CLI、原生 PostgreSQL 16 或 Redis 服务。数据库测试使用 **PGlite 0.5.8：PostgreSQL 18.3 WASM**，加载真实 vector / pg_trgm 扩展，通过 PostgreSQL 协议和 SQLAlchemy asyncpg 执行实际 SQL、约束、事务和迁移。

PGlite 的 socket 多路复用适配器存在 asyncpg 关闭握手和预处理语句名称兼容问题。只在 `scripts/pglite_runner.py` 中对经过版本确认的本机 `127.0.0.1:55432` 测试适配器处理连接关闭和唯一语句名称，生产数据库连接代码没有这些补丁。本次数据保存在 workspace 父目录的 `.tools/pglite/data`，不包含在源码压缩包中。

需要复现本机兼容测试时，从 monorepo 根目录运行：

```powershell
npm install --prefix ../.tools/pglite @electric-sql/pglite @electric-sql/pglite-socket @electric-sql/pglite-pgvector
../.tools/pglite/node_modules/.bin/pglite-server.cmd --db=../.tools/pglite/data --host=127.0.0.1 --port=55432 --extensions=@electric-sql/pglite-pgvector:vector,pg_trgm --max-connections=64
```

另一个 PowerShell 终端：

```powershell
$env:PYTHONPATH = "$pwd;$pwd\backend"
$env:DATABASE_URL = 'postgresql+asyncpg://postgres:postgres@127.0.0.1:55432/postgres?ssl=disable'
$env:TEST_DATABASE_URL = $env:DATABASE_URL
python scripts/pglite_runner.py --module alembic -c backend/alembic.ini upgrade head
python scripts/pglite_runner.py -q backend/tests
python scripts/pglite_runner.py --module scripts.verify_collection --source 'Resource World' --require-entities
```

这套测试服务器仅用于本地验证；生产部署使用 Compose 中的 PostgreSQL 16 + pgvector。

## 尚未在本机验证

原生 PostgreSQL 16 环境的在线降级/再升级、Redis 分布式限速和 Celery Worker/Beat 的真实并行联调、三类 Docker 镜像构建、Prometheus/Grafana 容器运行、真实 LLM、真实 BGE-M3 和重排模型均未在本机执行。现有 CI 已编排 PostgreSQL 16、迁移检查、前端构建和容器检查；尚未连接 GitHub 远端或触发 CI，不能称为 CI 已通过。

付费/认证信源的生产启用还需要正式数据合同、凭据、公司白名单和实际接口字段约定。目录中的关闭状态和 parser_config 备注保留了这些限制。
