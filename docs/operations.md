# 启动、配置与运维

所有 Compose 命令显式传 `--env-file .env -f deploy/docker-compose.yml`，避免在 deploy 目录使用了错误 env 文件。根目录 `.env` 不提交，`.env.example` 可提交；LLM key 使用 SecretStr 包装，只从环境注入。

## 配置分组

- 存储：DATABASE_URL 必须使用 postgresql+asyncpg；REDIS_URL 用于缓存/锁/限流，CELERY_BROKER_URL 与 CELERY_RESULT_BACKEND 分库。配置 QDRANT_URL 后启用可重试的向量镜像；为空时使用 pgvector。Qdrant 故障不会丢失 PostgreSQL 中的向量。
- 模型：LLM_BASE_URL 为服务商兼容接口的根地址，客户端追加 `/chat/completions`；地址不一定含 `/v1`。LLM_MODEL 与服务商一致，支持 JSON 响应。EMBEDDING_MODEL=BGE-M3、RERANKER_MODEL=bge-reranker-v2-m3，容器中的 ML_ENABLED 与 INSTALL_ML 同时开启。MODEL_CACHE_DIR 可复用本地权重，首次下载只获取所需 PyTorch 文件。
- 采集：FETCH_INTERVAL 为全局建议默认，新建源可设独立 fetch_interval；FETCH_TIMEOUT 默认 30s，最大响应 5MB，max_items 默认 10、上限 20，正文最多存储 100,000 字符；自定义 USER_AGENT 使用可联系的正式域名。
- 发布：AUTO_PUBLISH 默认 false，质量门槛 70 且相关度大于 0。政策初始影响分 0 表示未评估。
- 安全：APP_ENV=production 时必须随机 SECRET_KEY ≥32 字符和确切 CORS 域名；数据库、Grafana 密码更换；PUBLIC API 网关需配置 TLS 与访问域名。当前端口绑定 127.0.0.1 适用于本机，外部部署需通过受控 TLS 入口。

配置使用 Pydantic v2 Settings 验证，CORS_ORIGINS 为 JSON 数组。[官方配置说明](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

## 信源配置

RSS/Atom：type=rss，公开订阅地址，按 source.language 和 source.region 记录已知信息。优先尝试网页正文，失败可保留源 RSS 中公开暴露的正文；不绕过登录或 robots 抓取网页。

静态正文页：type=web。动态正文页额外 `config_json={"dynamic":true}`。当前不实现自动发现整站新页面、翻页和浏览器登录态。

JSON 文章 API 示例：

```json
{
  "records_path": "data.items",
  "max_items": 10,
  "fields": {
    "title": "headline", "content": "body", "url": "link",
    "published_at": "published", "country": "country_name",
    "effective_date": "effective_date"
  }
}
```

价格 API 使用 category=price，records_path 指向记录数组，字段映射 mineral/price/unit/currency/date。单位和币种必须显式；缺失/不合规则事务失败，不推断单位。价格序列不能混用 USD/CNY 或吨/磅。原始响应同时作为证据快照入文章库，按同样审核流程发布。

源不支持可信凭据注入时不要把 API key 放到 config_json；有授权行情/登录网站时应新增适配器从环境或 secret store 获取凭据。

## 迁移、恢复与备份

```text
docker compose --env-file .env -f deploy/docker-compose.yml run --rm migrate
docker compose --env-file .env -f deploy/docker-compose.yml exec api alembic current
docker compose --env-file .env -f deploy/docker-compose.yml exec api alembic check
```

升级服务先备份数据库，查看迁移 SQL，再在维护窗口执行。降级 `alembic downgrade base` 会删除业务表，仅适用于空开发/测试数据库；不要在真实语料库作为常规回滚。生产代码回滚优先兼容旧 schema，破坏性迁移采用分阶段方案。

PostgreSQL 采用定期 pg_dump 或连续 WAL/PITR，保留模型版本与环境配置。Redis AOF 持久化队列，但业务事实以 PostgreSQL 为准；补偿任务扫描 committed pending 记录。演示数据只能用于隔离环境，示例域名链接不会提供真实文章。

Beat 只运行一个实例。任务 soft/hard limit 为 540/600 秒，锁 TTL 660 秒，Redis visibility_timeout 3600 秒。单篇超长翻译/模型冷加载超时会失败，缩小源批量、预热模型，必要时调整任务/锁/可见性超时并保持锁覆盖整个执行窗口。硬杀后可能保留 running 记录，依据 worker 状态人工恢复；当前未包含自动 watchdog。

## CI/CD 与部署边界

GitHub 只发现仓库根 `.github/workflows`。deploy 下工作流是用户所需结构副本，CI 检查两份完全一致。仓库建立后把 miningintel 目录作为 Git 根；工作流默认为 main。

CI 配置 Linux、Python3.12、Node22、PostgreSQL16+pgvector、Redis 和 Qdrant 服务，验证迁移、业务查询、权限、采集幂等、价格回填与镜像过滤。模型单元测试注入测试编码器，真实 BGE 另行预热验证。三种 Dockerfile 均构建，workflow_dispatch 可发布 GHCR 镜像（基本镜像不包含重型 BGE）。API 完整 ML 运行需 INSTALL_ML=true，避免 query encoder 依赖缺失。

生产服务仍需目标服务器/集群、TLS、域名、镜像拉取策略和 secrets。没有这些信息时不编造可用的线上地址，也不写硬编码服务器凭据。前端使用 Next standalone 自托管，[官方部署说明](https://nextjs.org/docs/14/app/building-your-application/deploying)。Next14 依照用户版本要求固定 14.2.35，选用该系列已发布的修复版本；上线前根据维护策略检查后续公告并规划受支持版本升级。[版本修复公告](https://nextjs.org/blog/security-update-2025-12-11)

## 已知扩展项

当前实现尚无真实矿业语料的质量基准、生产压测、GPU 部署验证、全部站点逐源适配、商业行情凭据、完整 GIS 或政策影响因果评估。热点 SQL 读取 48h 已发布记录，数据增长后可改为增量聚合表。向量已支持内容变更、增量索引和全量重建；历史正文版本仍需独立归档。

## 阶段 3 运行说明

网站读取 `/api`，第三方读取 `/api/open` 并携带个人 API Key；Key 从已登录账户创建、只展示一次，数据库只保存摘要。SlowAPI 使用路由完成后执行的全局依赖，兼容新旧 FastAPI 路由结构。缓存使用 Redis，热点 300 秒、趋势 1800 秒、简报 3600 秒；更新语料后共享版本失效，避免不同 API 实例继续展示撤回内容。

当前周期日报/周报/月报每 15 分钟检查证据变化，模型生成在数据库事务外执行，提交前重新核对来源哈希。手动生成使用 `python -m scripts.generate_digest --kind weekly`，本机 PGlite 使用 `python -m scripts.pglite_runner --module scripts.generate_digest --kind weekly`；该命令不发送邮件。模型失败时 GET 继续提供真实统计和原文摘录。

邮件服务已实现 SMTP、用户主动订阅和唯一投递记录，但默认关闭。运营方配置 SMTP_HOST/SMTP_PORT/SMTP_FROM、TLS/凭据和 EMAIL_NOTIFICATIONS_ENABLED 后，后台任务只向选择接收邮件的用户发送匹配资料。此次仅验证模拟 SMTP，没有发送真实邮件。

当前 Windows API 为 8001，前端为 3000，Redis 为 WSL 6380，开发数据库为本机 PGlite 55432。启动助手不自动终止其他项目的进程；基础服务需先运行。生产 Compose 使用 PostgreSQL 16、容器内部 Redis 6379，覆盖 Windows 本机路径和端口。当前真实数据、运行截图与性能范围见 [阶段 3 验证记录](phase3-verification.md)。
