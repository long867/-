# 阶段 3 验证记录

验证日期：2026-10-11。前端 http://127.0.0.1:3000，API 文档 http://127.0.0.1:8001/docs。

## 真实资料与遗留修复

开发库共 20 篇真实原始资料，14 篇已发布：10 条生意社碳酸锂现货记录、4 篇 Resource World 英文新闻。已知演示信源、演示文章、价格和政策已清理；测试夹具在测试结束后删除，不作为首页数据。

4 篇已发布英文稿的原文/译文数字校验全部通过，中文摘要分别为 113、148、177、184 字。数字、百分比、币种、单位与数量级校验已覆盖模型漏值、改值、重复占位符、分段边界和嵌套 JSON 响应。其余 6 篇模型仍产生缺值或不一致结果，保留 pending 和失败原因，未降低校验标准发布。

真实价格为 2026-09-18 至 2026-10-09 的 10 个观测，最新 121000.00 CNY/吨。产品口径为碳酸锂现货，来源未注明等级，不能称电池级或锂矿石。重复抓取 fetched=10、duplicates=10、new=0、errors=0。原表价格列与期货列明确区分，保留日期、单位说明和来源页面快照。最新抓取页可能是滚动首页，文章链接使用稳定日期页。

已发布资料使用实际 BGE-M3 编码，向量维度为 1024；4 篇新闻和 10 条价格均完成索引。数据快照见 [phase3-data-verification.json](phase3-data-verification.json)。

## 自动回归

- 后端 126 项测试通过：过滤、分页、稳定排序、UTC 日期边界、字面搜索、待审核/撤回隔离、事件和政策关联、缓存命中及失效、Key 摘要/撤销/所有权、订阅权限、模拟 SMTP 去重、翻译/摘要/问答证据、表格价格召回、嵌套路由限流。
- Ruff 检查通过，含 scripts/browser_smoke.py 的 E501。
- TypeScript 类型检查通过；前端 3 项 SSE 测试通过；Next.js 生产构建通过，包含新增业务页面。
- 真实库升级至 0004_business_api，alembic check 无模型漂移；CI 配置副本一致。
- OpenAPI 共 90 个路径，包含规范 API、开放 API、咨询和兼容接口；网站 API 文档声明匿名读取，开放 API 强制 X-API-Key。

本机后端回归示例，从项目根目录运行；这些环境变量仅影响当前测试终端：

```powershell
$env:ML_ENABLED='false'
$env:LLM_API_KEY=''
$env:RATE_LIMIT_BACKEND='memory'
$env:API_RATE_LIMIT='10000/minute'
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:55432/postgres'
.\.venv\Scripts\python.exe -m scripts.pglite_runner backend/tests -q
.\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml backend pipeline scripts
```

在新的正常终端运行真实服务和浏览器验证，不使用上述测试覆盖变量：

```powershell
.\run_api.ps1
# 另一个终端
.\run_web.ps1
# 服务运行后
.\.venv\Scripts\python.exe -m scripts.business_browser_live_smoke
.\.venv\Scripts\python.exe -m scripts.pglite_runner --module scripts.rag_browser_live_smoke
.\.venv\Scripts\python.exe -m scripts.verify_business_api
```

## 实际浏览器与问答

不拦截 HTTP、不替换真实 API 的 Playwright 验证通过：首页 14 条资料，10 条/页翻页、关键字过滤、质量/发布时间排序、真实价格链接、矿种/事件/政策/趋势页面、周报和 390px 移动端。没有 JavaScript 异常、API 错误或横向溢出。记录见 [phase3-browser.json](phase3-browser.json)，截图见 [桌面](phase3-home.png)、[移动端](phase3-mobile.png)。

真实账号登录、SSE、原文卡片、追问和会话删除通过；临时账号与会话已删除。问题“2026年10月9日生意社碳酸锂现货报价是多少？请给出币种和单位。”得到 121000.00 元/吨的 grounded 回答和逐字证据。追问币种与单位沿用同一会话，仍为 grounded；天气问题精确返回“根据现有资料，未找到相关信息”。引用日期按 Asia/Shanghai 显示，避免日精度行情被 UTC 转换显示为前一天。见 [phase3-rag-verification.json](phase3-rag-verification.json) 与 [问答截图](phase3-rag.png)。

周报和月报均通过实际配置的 LLM 生成并入库，每份基于本周期 6 篇公开资料；GET 提供全部周期统计和来源。今日日报无已发布资料时显示空状态，模型不可用时提供真实证据摘录。没有发送真实邮件。

## 缓存与限流

7 个缓存端点分别连续测量 20 次，X-Cache=HIT，TTL 分别为热点 300 秒、趋势 1800 秒、简报 3600 秒，实测暖缓存 P95 均小于 200ms。逐端点原始结果见 [phase3-api-verification.json](phase3-api-verification.json)。性能是当前小语料本机结果，不代表生产并发容量。

Redis 限流真实请求返回 429，记录见 [phase3-rate-limit-verification.json](phase3-rate-limit-verification.json)。新版 FastAPI 使用懒加载嵌套路由，旧 SlowAPI 中间件不能发现业务处理器；已改为路由解析后执行的全局依赖，回归覆盖嵌套与不同文章 ID 共用配额。限流验证会暂时耗尽测试路由的每分钟配额，请等待窗口恢复。

## 环境与验证范围

本机为 Windows、Python 3.12、CPU BGE、PGlite PostgreSQL 18.3 兼容适配器、WSL Redis 6380。原生 PostgreSQL 16、Docker Compose 镜像、服务端 Qdrant、SMTP 真投递和生产压测未在本机执行；CI 已配置独立 PostgreSQL 16/Redis/Qdrant、迁移回归和镜像构建。Qdrant 本地测试提示 payload 索引不生效，服务端索引需部署后验证。

当前 LLM Key 可用，无需新增申请。自动邮件默认关闭，需要运营方 SMTP 配置和用户主动选择接收；其余待审核英文稿、商业行情授权和生产部署按 [运维说明](operations.md) 处理。
