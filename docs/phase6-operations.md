# 阶段 6：定时任务、监控与部署

## 定时任务

Beat 使用 Asia/Shanghai 时区和持久化调度文件，并以 Redis 90 秒租约确保只有一个调度器。Worker 使用 Linux prefork；2 GiB ECS 采用单并发，消费 celery、nlp、insights 三个队列。

- 采集调度：30 分钟，仍遵守信源单独的采集间隔、条件请求和失败冷却。
- 待处理文章恢复：15 分钟，不自动重试已经标记为终止的加工错误。
- 增量向量索引：1 小时；Qdrant 同步 outbox 恢复每 30 秒。
- 事件聚类：2 小时，近 7 天文章。
- 完整趋势分析：6 小时，24h/48h/7d 窗口；价格预警另每 5 分钟检查。
- 昨日日报：每日 08:00；上周周报：周一 08:00；上月月报：每月 1 日 08:00。
- 当前周期摘要：15 分钟，按周期幂等更新。
- 缓存与轮转日志清理：每日 02:00；只清理 MiningIntel 的过期任务索引、旧公共缓存代次、过期日志。
- 通知 outbox 恢复：1 分钟。

采集、加工、索引、聚类、趋势、报告等任务失败采用指数退避，最多重试 3 次。任务记录保留 7 天、最多 10,000 条，记录状态、耗时、重试次数和错误类型，不记录问题、文章内容、令牌或任务参数。Worker/Beat 的容器健康检查使用真实 Redis 心跳。

## 管理与监控

登录 `/admin` 可查看系统计数、队列长度、Worker/Beat 心跳、任务历史、调度配置；文章支持批量发布、隐藏和重新处理。重新处理先提交数据库状态及索引撤销，再发送消息，消息队列故障时由恢复任务补发。

Prometheus 采集 API 与 Worker；Grafana 自动配置 12 个面板，覆盖采集、新文章、翻译、问答、耗时、错误率、矿种与状态分布、任务耗时。Alertmanager 已接收配置，默认只在本机查看，不向未配置的外部渠道发消息。

告警规则包括连续采集失败 3 次、活跃信源超过 2 小时没有新增、API 5xx 比例超过 5%、问答完整生成 p95 超过 5 秒，以及服务指标不可用。冷启动无文章时不误判采集停滞。规则由 promtool 验证，包含触发与不触发测试。

API/Worker/Beat 输出 JSON 到 stdout 和各进程独立的轮转文件，默认保留 14 天；脱敏 API Key、认证头、数据库 URL 和异常正文。`deploy/filebeat.yml` 提供可选 ELK 对接，2 GiB 服务器默认不运行 ELK。

## Linux 部署

专用目录 `/opt/miningintel`；独立 Compose 项目名 `miningintel`；网站监听 3030，数据库、Redis、Qdrant 不向公网暴露。Prometheus 只绑定 `127.0.0.1:9091`，Grafana `127.0.0.1:3001`，Alertmanager `127.0.0.1:9093`。既有的 9090 项目不受影响。

新环境首次配置：复制 `.env.production.example` 为 `.env` 并填写独立数据库密码、SECRET_KEY、Grafana 密码及 LLM 设置。已有环境保留现有 `.env`。镜像可从本地审查构建后导入，或由 CI 生成。

```bash
cd /opt/miningintel
docker compose --project-name miningintel --env-file .env --env-file .images.env \
  -f deploy/docker-compose.yml -f deploy/docker-compose.production.yml \
  --profile monitoring --profile backup up -d --no-build --wait
```

`deploy/release.sh /opt/miningintel` 校验配置、互斥发布、运行迁移、检查 API/页面，再记录版本；失败时恢复前一版本镜像，不擅自降级数据库。提前导入全部镜像时设置 `MININGINTEL_IMAGES_PRELOADED=true`，脚本仍会检查所有镜像确实存在。

2 GiB ECS 启用 LLM 翻译与咨询、真实关键词检索，默认不在本机加载 BGE/重排序模型；`INSTALL_ML=false`、`ML_ENABLED=false` 明确显示实际检索模式。启用本地向量模型前需提供足够的内存或独立推理服务，不会生成假向量。

原有网站的删除仅限已核验的 `/opt/library-survey` 和 `/etc/systemd/system/library-survey.service`，并先验证 D 盘备份。其它项目、宿主 Nginx、MySQL 和 Docker 卷均保留。

## GitHub Actions

仓库 `.github/workflows/ci.yml` 是实际执行入口，`deploy/.github/workflows/ci.yml` 为经过校验的镜像副本。

必需 Secrets：`DEPLOY_HOST`、`DEPLOY_USER`、`DEPLOY_PORT`、`DEPLOY_SSH_KEY`、`DEPLOY_KNOWN_HOSTS`。Variables：`DEPLOY_DIR=/opt/miningintel`、`DEPLOY_ENABLED=true`。应用与云备份密钥只放服务器 `.env`，不进入源码、构建镜像或 Actions 日志。

CI 在测试成功后发布 `ghcr.io/<owner>/miningintel-<image>:<git-sha>`，部署 job 用短期 GITHUB_TOKEN 下载镜像，校验传输包、导入镜像，再运行发布脚本。部署 job 串行执行，固定 SSH 主机公钥。首次切换之前保持 `DEPLOY_ENABLED=false`。

## PostgreSQL 备份

备份容器每天 03:00 执行 PostgreSQL 16 `pg_dump` 自定义格式，运行 `pg_restore --list`，上传 S3/OSS 后以 HEAD 校验文件长度和 SHA256，全部通过才记录成功状态。临时文件在成功和失败后均清理，失败重试最多 3 次。使用 HTTPS，OSS endpoint 示例为成都区域；对象前缀限定在本项目。

默认 `BACKUP_ENABLED=false`。启用云备份还需填写 `BACKUP_S3_BUCKET`、`BACKUP_S3_ENDPOINT`、`AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`、`AWS_DEFAULT_REGION`；对象保留期由存储桶生命周期配置。未经真实凭据和上传验证，不宣称云备份成功。

恢复时先在独立临时数据库执行 `pg_restore --no-owner --no-privileges` 并校验表和数量，再按维护计划切换；不直接覆盖运行中的数据库。邮件/Webhook 也需要对应 SMTP/渠道配置，未启用时不发送。

## 本机 D 盘

```powershell
cd D:\MiningIntel\miningintel
. .\scripts\use_d_drive.ps1
.\run_preview_db.ps1
# 分别在新终端启动
.\run_api.ps1 -Port 8001
.\run_web.ps1 -Port 3000 -Production
```

虚拟环境与 Python 在 D 盘，模型缓存位于 `D:\MiningIntel\.model-cache`；WSL/Docker 数据在 `D:\MiningIntelRuntime\Ubuntu`。运行日志、镜像包、验证产物在项目 `artifacts/`，不进入公开源码包。仅清理本项目生成的无用构建镜像与传输包，不清理其它项目数据。
