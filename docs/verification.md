# 初始化验证记录

日期：2026-10-10（Asia/Shanghai）。本记录区分源码验证、虚构数据的浏览器验证和未具备运行环境的检查，不将它们合并为“生产联调已完成”。

## 已执行并通过

- 后端 `pytest -q`：**41 passed，6 skipped**。覆盖来源规范化、私网请求拒绝、重定向校验、体积限制、304、JSON 价格映射、原文分块与重复文字定位、实体识别、双语检索词扩展、RRF、来源多样性、向量尺寸/有限性、密码与 JWT、CORS、敏感参数隐藏、公开事件摘要隔离、模型引用校验和失败降级。
- Ruff：全部后端、pipeline、迁移、测试及脚本 check / format --check 通过，49 个 Python 文件已格式化。
- Alembic：`upgrade head --sql` 成功生成 PostgreSQL DDL，包含 vector/pg_trgm、12 张业务表、UUID、timestamptz、JSONB、text[]、vector(1024)、检查/唯一/外键约束和 GIN/HNSW 索引。
- FastAPI：应用导入与 OpenAPI 生成正常；基础路径和认证 schema smoke test 通过，健康检查包含检索模式。
- 前端：`npm run typecheck`、`npm run build` 通过；Next 14.2.35 生成资讯、登录、咨询、订阅、管理等页面，standalone 构建完成。
- Edge + Playwright：桌面 1440px / 手机 390px，筛选、正文展开、事件页、单序列价格图、登录、咨询发送与原文引用展开、管理后台页面通过；没有 JavaScript pageerror，手机文档无横向溢出。

浏览器测试通过 `scripts/browser_smoke.py` 显式拦截 API，返回带“演示数据，非真实新闻”标签的虚构资料。它验证页面交互和响应契约，**不等同于真实数据库、采集源或 LLM 的端到端测试**。正常运行代码没有这些 API mock。

界面截图：[桌面](previews/frontend-desktop.png)、[手机](previews/frontend-mobile.png)，均为虚构资料。

## 未在本机执行

本机没有 Docker CLI、PostgreSQL 和 Redis 服务；六项 PostgreSQL integration 测试因此跳过。未实际构建 Docker 镜像，未在线执行数据库迁移/降级、HNSW 查询计划、Celery worker/Beat 连通、监控容器或真实信源采集。也未下载/加载重型 BGE 模型，未调用真实 LLM。

这些步骤已在 `.github/workflows/ci.yml` 编排：真实 PostgreSQL16+pgvector 测试、Alembic schema drift 检查、升级/降级/再升级、前端构建、Compose 检查与三镜像构建。**工作流已生成，但本次没有 GitHub 远端，因此未实际触发或通过 CI。**

运行 PostgreSQL 集成测试需要独立测试库、先执行迁移，并设置 TEST_DATABASE_URL。测试用事务回滚或显式清理，不要把生产库作为测试库。

## 功能边界

详见 product.md 与 operations.md。初始工程提供可构建和扩展的基础实现；真实行情授权、邮件投递、商业 API key、精确矿区 GIS、查询时间意图、政策影响评估、事实支持率/召回率标注和生产容量仍需后续实施。引文位置校验不能替代语义事实核查。
