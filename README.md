# MiningIntel

阶段 5 已加入统计热点、价格预警、政策主题、完整周期自动报告、历史归档、SMTP/Webhook 和站内消息中心。启动与配置见 [阶段 5 说明](docs/phase5-insights.md)。前端保持 `http://127.0.0.1:3000`，报告在 `/digest`，趋势在 `/trends`，登录后从消息中心查看通知。

全球矿产资源资讯聚合与咨询平台的 monorepo 工程初始化。提供产品定义、架构说明、可构建前端、异步 API、可逆数据库迁移、采集加工任务、带原文定位的问答与本地部署配置。

## 架构

```mermaid
flowchart LR
  S[多语言 RSS / 网页 / JSON API] --> F[httpx / feedparser / Playwright]
  B[Celery Beat · Asia/Shanghai] --> Q[Redis 队列与锁]
  Q --> F
  F --> P[正文提取 · 去重 · 翻译 · 摘要 · 实体识别]
  P --> E[事件聚类 · 质量评分 · 人工审核]
  E --> DB[(PostgreSQL 16 + pgvector)]
  DB --> I[BGE-M3 · 512 token · 增量索引]
  I --> DB
  I --> O[事务同步队列 · 重试]
  O --> V[(Qdrant · 文章与原文片段)]
  V --> H
  DB --> H[关键词 / 向量召回 · RRF · BGE 重排]
  H --> A[LLM 咨询 · 原文引用校验]
  DB --> T[热点统计 · 价格异动 · 日 / 周 / 月报]
  UI[Next.js 14 · 卡片 / 时间线 / 地图] --> N[Nginx]
  N --> API[FastAPI /api · /api/open]
  API --> DB
  API --> A
  API --> T
  API --> C[Redis · 缓存与速率限制]
  API --> M[Prometheus → Grafana]
```

**PostgreSQL 是权威数据源，Qdrant 是可重试的检索镜像**：文章向量、原文片段、索引版本与同步任务在同一事务中提交。Qdrant 故障时保留 PostgreSQL 向量，检索降级至 pgvector；所有镜像命中都会回查数据库中的发布状态、筛选条件和版本。LlamaIndex 负责句段切分、异步混合检索和查询引擎，生成的论点经过来源、逐字引文和数值校验。

## 文件入口

阶段 3 已增加完整情报 API、真实锂价采集、Redis 缓存、开放 API Key、当前周期简报与邮件订阅。`/`、`/minerals`、`/events`、`/policies`、`/trends` 均读取真实 API。详见 [阶段 3 说明](docs/phase3-business.md)。

阶段 4 已完成前端工作台：明暗与中英切换、热点卡片、URL 多选筛选、无限滚动、真实行情图与地图、文章详情、搜索、简报、收藏、订阅弹窗、SSE 问答、后台表单和 PWA。查看 [阶段 4 页面与验证说明](docs/phase4-frontend.md)。生产预览在构建后使用 `.\run_web.ps1 -Production`，网站仍运行在 3000。

当前 Windows 本地环境，从项目根目录打开两个 PowerShell 终端：

```powershell
# 终端 1：使用项目 Python 和 .env
.\run_api.ps1
# 终端 2：沿用 3000 端口，已运行时直接提示地址
.\run_web.ps1
```

打开 [网站](http://127.0.0.1:3000/) 和 [API 文档](http://127.0.0.1:8001/docs)。数据库、Redis 需已启动。本机使用 PGlite 55432 与 WSL Redis 6380；生产/全新部署使用下方 Compose 的 PostgreSQL 16。兼容启动器只用于核实过的本机 PGlite。

- `docs/product.md`：用户、产品信息架构、MVP、后续阶段与验收指标。
- `docs/architecture.md`：数据模型、检索、任务一致性、安全边界、扩容策略。
- `docs/operations.md`：配置、部署、迁移、采集、运维和已知边界。
- `docs/api.md`：开放 API、认证、筛选、任务和问答示例。
- `backend/app/main.py`、`core/config.py`：API 入口与 Pydantic Settings。
- `backend/app/models/entities.py`：全部模型；`backend/alembic/versions/0001_initial.py`：固定版本的建表迁移。
- `pipeline/`：RSS / 静态与动态网页 / JSON API、spaCy 规则实体识别、加工与事件聚类。
- `frontend/app/`：资讯中心、咨询、订阅、登录和管理后台。
- `deploy/`：Compose、Nginx、Prometheus 和预配置 Grafana 仪表盘。
- `.github/workflows/ci.yml`：GitHub 能发现的实际工作流；`deploy/.github/workflows/ci.yml` 保留用户要求的同内容副本。

## Windows 网页启动

阶段 2 的完整配置与索引命令见 [智能加工与 RAG 使用说明](docs/phase2-rag.md)。本地 `.env` 位于 `miningintel/.env`，和本 README 同级；密钥仅填入本地文件，不提交或打包。

真实模型、API 与页面联调的结果和环境范围见 [阶段 2 验证记录](docs/phase2-verification.md)。咨询页位于 `/chat`，登录或注册后可以开始提问。

在 **miningintel 根目录**运行以下前端入口。需先运行 API；本机预览 API 使用 `127.0.0.1:8001`：

```powershell
.\run_web.ps1
```

打开 [http://127.0.0.1:3000/](http://127.0.0.1:3000/)。重复执行时，脚本识别已有 MiningIntel 页面并直接复用，不会再启动第二个 Next 实例。如果端口上是其他服务或页面异常，会停止并显示原因。前端新启动后需保持终端运行；可用 `-ApiUrl` 指定其他 API 地址。

`EADDRINUSE` 表示重复占用同一端口。失败的第二个 Next 开发实例也可能影响共享 `.next` 缓存，因此应使用此入口作启动检查。API 根路径没有网页路由，API 文档位于 [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)。

## Windows 采集快速启动

已有项目 `.venv` 时，在 **miningintel 根目录**执行；不需要激活环境或安装全局 `uv`：

```powershell
.\run_pipeline.ps1 --list-sources
.\run_pipeline.ps1 --source 'Resource World' --dry-run
```

脚本固定使用 `.venv\Scripts\python.exe`，切换到项目根目录，并透传所有采集参数与退出码。从上一级目录也可以运行 `.\miningintel\run_pipeline.ps1 --dry-run`。`--dry-run` 不连接数据库，但会请求实际信源并在配置 LLM 后调用模型。

如果本机代理 DNS 把信源解析到 `198.18.x.x` 等非公网地址，采集器会拒绝请求。可在当前终端显式选择项目支持的公共 DNS-over-HTTPS，再重试：

```powershell
$env:FETCH_DNS_RESOLVER = 'https://1.1.1.1/dns-query'
.\run_pipeline.ps1 --source 'Resource World' --dry-run
```

若环境未安装完整依赖或出现 `No module named pip`，在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m ensurepip --upgrade --default-pip
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e backend
.\.venv\Scripts\python.exe -m pip check
```

`ensurepip` 使用 Python 自带的安装包为当前解释器补装 pip，见 [Python 官方文档](https://docs.python.org/3.12/library/ensurepip.html)。依赖文件为 `requirements.lock` / `requirements-dev.lock`，没有 `requirements.txt`。使用 `python -m pip` 或显式 `.venv` 解释器，避免裸 `pip` 指向 Conda。项目根目录没有 `pyproject.toml` / `uv.lock`，当前采用锁定 requirements 安装方式。

也可以直接运行 `.\.venv\Scripts\python.exe -m pipeline.run_pipeline --dry-run`；用 `-m` 从项目根目录启动，确保 `pipeline` 包可被导入。网络解析问题和生产入库命令见 [阶段 1 使用说明](docs/phase1-collection.md)。

## PyCharm 开发

本机在上一级 `mineral resources advice` 目录打开工程。该工程已配置 `MiningIntel Python 3.12` 解释器，指向 **miningintel 内层**的 `.venv\Scripts\python.exe`，并将 `miningintel` 和 `miningintel/backend` 用于解析 `pipeline` 与 `app` 包。上一级目录的 Python 3.14 `.venv` 没有本项目依赖。

修改解释器配置后重启 PyCharm，让 IDE 加载新的 SDK 与索引。顶部运行配置选择 **MiningIntel RSS Preview**，即可用模块模式对 Resource World 执行 `--dry-run`；该配置不写数据库。`pipeline/run_pipeline.py` 同时支持直接运行文件，自动补齐本地 `pipeline` 包的搜索路径。

若在另一台机器打开项目，选择已有 Python 3.12 环境并安装上述锁定依赖，见 [PyCharm 解释器官方说明](https://www.jetbrains.com/help/pycharm/configuring-python-interpreter.html)。网页服务仍按 Docker 或原生前端/API 的启动说明运行。

## Docker 启动

安装 Docker Desktop（Linux containers）与 Compose v2，以下命令均在 **miningintel 根目录**执行。首次构建需要下载 Python/Node 依赖和 Chromium。

```powershell
Copy-Item .env.example .env
# 编辑 .env 的数据库密码、SECRET_KEY 和模型配置。
docker compose --env-file .env -f deploy/docker-compose.yml up --build -d
docker compose --env-file .env -f deploy/docker-compose.yml ps
```

Compose 中的数据库 URL 使用容器服务名 `postgres`、`redis`，密码必须与 `POSTGRES_PASSWORD` 一致。密码含特殊字符时对 URL 中的密码部分做百分号编码。迁移作为一次性服务运行成功后，API/worker/Beat 才启动。

访问：应用 [http://localhost:8080](http://localhost:8080)，API 文档 [http://localhost:8080/docs](http://localhost:8080/docs)，健康检查 `/health/live`、`/health/ready`。

创建管理员（密码交互输入，不进入命令参数）：

```powershell
docker compose --env-file .env -f deploy/docker-compose.yml exec api python -m app.cli create-admin admin@example.com
```

首次数据库为空。登录管理员账号后，在“管理后台”添加实际授权信源并触发采集；默认 `AUTO_PUBLISH=false`，加工完成后手动审核发布。页面仅展示真实采集与审核后的资料，尚无数据时显示空状态。

## 模型模式

默认 `ML_ENABLED=false`，可运行双语词典扩展的关键词检索、原文证据摘录、规则实体提取与保守事件分组。未配置 LLM 时，不会把外文冒充中文译文。此模式适合先验证 API 与采集流程。

启用完整 AI 流程：填写可兼容 `/chat/completions` 和 `response_format=json_object` 的 `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`，同时设 `INSTALL_ML=true`、`ML_ENABLED=true` 后重建 `api`、`worker`。BGE 首次加载会下载模型，默认 CPU/FP32；应按并发和语料量配置内存/GPU，测量后决定独立推理服务。模型未安装或下载失败会暴露失败状态，不会写入假向量。

问答只使用 **已发布的全部文本语料**，包括新闻、研报、政策、公司公告，以及价格 API 的原始响应快照。规范化 `price_records` 供图表和同比口径查询；管理员手动录入的价格只进入结构化表。模型输出的引用编号和逐字引文必须通过校验，否则返回证据摘录。引文校验保证来源和位置真实，不能自动证明模型论点被引文完整支持。

## 原生开发

Python **3.12**，Node **22**，PostgreSQL 16（启用 `vector`、`pg_trgm`），Redis 7。本次初始化在 Windows 的 Python 3.12 虚拟环境中验证。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m ensurepip --upgrade --default-pip
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e backend
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = (Get-Location).Path
$env:DATABASE_URL = 'postgresql+asyncpg://miningintel:your-password@localhost:5432/miningintel'
$env:REDIS_URL = 'redis://localhost:6379/0'
$env:CELERY_BROKER_URL = 'redis://localhost:6379/1'
$env:CELERY_RESULT_BACKEND = 'redis://localhost:6379/2'
Set-Location backend
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

另一个终端在 frontend 执行 `npm ci`、`npm run dev`，访问 [http://localhost:3000](http://localhost:3000)。Next 开发服务器把 `/api/*` 转发到 localhost:8000。`API_INTERNAL_URL` 在 Next 构建时确定；生产 Compose 通过 Nginx 直接代理 API。

在设置了同样环境变量的终端，从 backend 运行任务：

```text
celery -A app.tasks.celery_app:celery_app worker -Q celery,nlp -l INFO
celery -A app.tasks.celery_app:celery_app beat -l INFO
```

Celery 正式运行采用 Linux 容器。Windows 原生仅用于开发，可加 `--pool=solo`，不作为生产部署。动态网页额外执行 `playwright install chromium`。重型 ML 依赖通过 `pip install -e 'backend[ml]'` 安装；基础依赖和开发依赖分别锁定。

## 测试与 CI/CD

```powershell
# backend 目录
pytest -q
ruff check --config pyproject.toml app tests alembic ../pipeline ../scripts
ruff format --check --config pyproject.toml app tests alembic ../pipeline ../scripts
alembic upgrade head --sql
# 有独立测试数据库时设置 TEST_DATABASE_URL，先迁移，然后再次 pytest。
# frontend 目录
npm run typecheck
npm run build
```

CI 在真实 PostgreSQL 16 + pgvector、Redis、Qdrant 上执行测试、`alembic check` 和升级/降级/再升级，随后构建 API、Worker、前端、备份四种镜像。main 推送发布 Git SHA 镜像；启用 `DEPLOY_ENABLED` 后，以专用 SSH 密钥部署到 Linux。GitHub runner 使用自己的短期令牌下载私有镜像后传输到服务器，服务器无需保存 GHCR 个人令牌。发布有互斥锁、健康检查和前一版本镜像回退。配置说明见 [阶段 6 运维说明](docs/phase6-operations.md)。

监控：`docker compose --env-file .env -f deploy/docker-compose.yml --profile monitoring up -d`；Prometheus 默认本机 9090，可通过 `PROMETHEUS_PORT` 改端口。ECS 配置使用 9091，保留已有的 9090 网站；Grafana 本机 3001，账户 admin，密码取 `.env`。Nginx 不向公网代理 `/metrics`。

本机项目现位于 `D:\MiningIntel\miningintel`，Docker 的 WSL 数据位于 `D:\MiningIntelRuntime\Ubuntu`。执行 `. .\scripts\use_d_drive.ps1` 后，项目临时文件及新增 pip/npm/uv/Playwright 缓存使用 D 盘。已迁移的虚拟环境可以直接运行 `python -m pip`。编辑器打开的旧目录仍可能被占用，请从 D 盘目录打开项目。

阶段 0 的验证记录见 `docs/verification.md`。阶段 1 已实现真实 RSS 采集、增量状态、分页、去重、翻译与实体加工、事件聚类及 Worker 指标，使用说明见 [docs/phase1-collection.md](docs/phase1-collection.md)。本机已完成 PGlite PostgreSQL 兼容环境的在线迁移与采集入库验证；PostgreSQL 16、Redis/Celery 和容器部署检查仍由具备环境的 CI 执行，详见 [阶段 1 验证记录](docs/phase1-verification.md)。
