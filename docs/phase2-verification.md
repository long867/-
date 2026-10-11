# 阶段 2 验证记录

验证日期：2026-10-11。本记录区分运行结果、测试夹具和未覆盖的生产环境。

## 已验证的功能

- 后端完整测试 96 项通过，Ruff 检查、80 个 Python 文件格式检查和 pip check 通过。覆盖采集、加工、检索、权限、原文引用、会话隔离和 SSE。pgvector 测试验证关键词不重合的语义召回；Qdrant 测试验证过滤、重试、旧片段替换、版本不一致与撤回文章拦截。
- BGE-M3 实际下载并在 CPU 上生成 1024 维非零有限向量，索引 tokenizer 使用 512 token 上限。bge-reranker-v2-m3 实际评分中，矿价相关段落为 0.946694，天气段落为 0.000016。
- 实际 BGE、pgvector、BGE reranker 与已配置的 GLM-4-Flash 一起完成查询引擎验证：价格问题、追问、逐字引用与原文位置校验均通过；天气问题返回“根据现有资料，未找到相关信息”。价格事实使用明确标注的临时虚构资料，记录在 finally 中删除，不是实际行情。
- 前端类型检查、生产构建和 3 项 SSE 解析测试通过；字节级拆分 UTF-8、CRLF、错误响应、异常结束不会被误判为成功。
- 浏览器夹具覆盖桌面/移动端页面、筛选、价格、管理与咨询。另一次真实前后端浏览器验证使用临时账号登录，验证 SSE、天气提示、演示语料的引用卡片/原文链接和删除会话，JavaScript 错误为 0；临时账号及会话已清理。
- 数据库迁移已到 0003_vector_index，alembic check 未发现 schema 差异；docs/schema.sql 包含完整离线迁移 SQL。源码压缩包排除 .env、密钥、模型缓存及依赖目录。

## 当前运行环境

前端：http://127.0.0.1:3000/，咨询页：http://127.0.0.1:3000/chat。API：http://127.0.0.1:8001/docs；/health/live 返回 ok 与 retrieval_mode=hybrid。本地 .env 已配置 LLM，ML_ENABLED=true，模型缓存位于项目外层 .model-cache/hub。

此机器使用 Python 3.12、CPU PyTorch 和 PGlite 18.3 + pgvector（127.0.0.1:55432）。PGlite 是本地兼容性验证环境，不替代原生 PostgreSQL 16 的生产验证；scripts.pglite_runner 仅对确认的本地 PGlite 连接应用适配。

本地没有运行 Redis 和 Qdrant 服务端。预览明确采用 RATE_LIMIT_BACKEND=memory；生产配置禁止该模式。Qdrant URL 为空时保留同步任务，pgvector 仍可检索。/health/ready 因 Redis 缺失返回 503，避免把预览环境表示为生产就绪。

库内真实 Resource World 文章经过采集并保留原文，发布仍受审核控制；界面中既有 8 篇明确标注的虚构演示资讯。没有真实的已发布 2026 年锂矿价格资料，因此该问题在当前语料下应返回资料不足，不用项目新闻或演示数字补充市场结论。

实际 API 对“2026年锂矿价格走势如何”的验证已返回 insufficient、上述固定提示与空 sources。8 篇演示文章已使用真实 BGE 写入向量，便于体验检索；其标识和虚构说明保持在原文及回答中。

历史英文资料补加工不是全部通过：GSilver 报道在真实 GLM-4-Flash 调用中多次出现数字不一致，被质量校验拒绝。原文及既有实体保留，文章保持 pending、processing_error=ValueError，未伪造成功译文或发布。其他 9 篇真实文章仍为 processed。更可靠的生成模型与真实语料质量评测仍需继续验证；现有 API Key 已可用于问答，无需重新申请来启用本地 BGE。

机器可读结果见 [phase2-verification.json](phase2-verification.json)。

## 重现方法

原生 PostgreSQL 测试环境运行：

```powershell
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://USER:PASSWORD@localhost:5432/miningintel_test'
$env:DATABASE_URL = $env:TEST_DATABASE_URL
$env:LLM_API_KEY = ''
$env:ML_ENABLED = 'false'
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml backend/tests -q
.\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml backend pipeline scripts
```

实际模型验收使用已配置模型的开发环境，不覆盖已存在 .env；scripts.rag_live_smoke 拒绝 production，创建并删除 UUID 范围内的测试资料：

```powershell
.\.venv\Scripts\python.exe -m scripts.rag_live_smoke
# 前端/API 已运行时；采用已存在的演示语料，不模拟 HTTP
.\.venv\Scripts\python.exe -m scripts.rag_browser_live_smoke
cd frontend
npm run typecheck
npm test
```

本机 PGlite 命令在 module 前加 runner，例如 `python -m scripts.pglite_runner --module scripts.rag_live_smoke`，并显式设置实际 DATABASE_URL。测试库不要指向生产库；此处没有执行清空既有语料的迁移降级。

## 待目标环境验证

CI 已配置 PostgreSQL 16 + pgvector、Redis 和 Qdrant 服务，但未从本机会话触发远端 CI。Docker 构建/启动、Linux Celery 并发、Qdrant 服务端 HNSW 性能与真实矿业问题 Recall@20 仍需对应环境验证。当前测试结果不代表生产容量、行业 NER 精度或真实矿价走势。
