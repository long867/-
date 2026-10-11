# 阶段 5：趋势洞察、完整周期报告与通知

所有业务结果来自 PostgreSQL 已发布文章、政策及原始价格记录。测试夹具只存在于自动清理的测试事务/账户中，不作为站点资讯或价格。

## 趋势计算

`pipeline/analyzers/hot_detector.py` 提供 24h、48h、7d 滚动窗口。历史基线使用不重叠窗口：24h 最多 28 个，48h 最多 14 个，7d 最多 8 个。至少 8 个完整窗口、至少 3 个非零历史窗口才能判断异常。当前报道量至少 3 篇，且超过历史均值两倍有效标准差，才标记 `is_hot=true`。有效标准差为历史总体标准差与 Poisson 稀疏计数下界的较大值。新站点和新矿种显示“历史样本不足”，不制造统计热点；趋势箭头只代表报道量相较前一个同长度窗口的变化。

热度为正 z 分数 ×20、上限 100；样本不足时页面显示“—”。迷你图来自最近七个真实日计数，包含真实的零值，不生成预测点。目前语料不足以支持七日窗口的长期异常判断，这是明确的数据状态。

`price_analyzer.py` 按矿种、产品、信源、单位、币种、现货/期货/基准分组。只对相隔一个日历日的原始报价计算**单日**预警，严格 `abs(change)>3%`，等于 3% 不预警。缺失报价日、不同口径及零基准不会产生虚假的单日涨跌幅。连续趋势指相邻报价的同向变化，间隔超过四天或持平会重置；页面显示“连续报价”，不会把报价次数解释成连续交易日。

预警等级按绝对变化量区分：3%–5% 绿色低级、5%–10% 黄色中级、≥10% 红色高级，与涨跌方向分开。阈值可用 `PRICE_ALERT_THRESHOLD` 设置，当前为 3。价格预警与价格趋势缓存 60 秒，采集或统计更新会使缓存失效。

`policy_tracker.py` 按支持文章的发布时间统计近一周政策，允许生效日期在未来。主题规则覆盖环保、出口限制、税收、许可与开发、供应链、投资与补贴；标签必须在标题/摘要中有文本依据，影响评分沿用入库值。

`event_ranker.py` 与事件 API 使用 `0.4×公开文章数 + 0.3×平均信源权威分 + 0.3×时效分`，上限 100。权威分为 1–10；时效分为 0–10，七天线性衰减。统计和展示标题均取公开文章，隐藏文章不能贡献分数或标题。报告内的事件只统计该报告周期的文章。

## 自动报告与归档

唯一 Celery Beat 的时区由 `DIGEST_TIMEZONE` 控制，默认 `Asia/Shanghai`：日报每天 08:00 生成昨日；周报每周一 08:00 生成上周一至本周一；月报每月 1 日 08:00 生成上月。所有结束日期均不包含当天，以**发布时间**归属文章，而非采集时间。

`daily_report.py`、`weekly_report.py`、`monthly_report.py` 共用 `common.py`。报告存储热点矿种 Top 5、统计热点信号、政策、价格异动、原始价格序列、事件回顾、每日报道量、统计及来源。价格图保留信源、币种、单位、产品口径；来源不足时显示实际数量，空周期保留明确的空报告。

LLM 生成事实句必须附逐字来源片段。编号、数字、百分比、单位和中文输出均通过现有校验后才保存；失败或没有模型配置时保留真实摘录，标记 `extractive`，不会伪称 AI 摘要。模型调用在数据库事务之外进行。报告以周期唯一约束及证据校验去重；全量文章的 ID/更新时间指纹覆盖摘要 Top 20 之外的证据。文章隐藏或修改会丢弃过期报告正文及分析，再从公开资料提供摘录。

API 兼容原来的当前周期简报，同时支持上一完整周期：

- `GET /api/digest/daily?scope=previous`，周报/月报同理；`scope=current` 是本期实时简报，API 默认仍为 current。
- `GET /api/digest/reports?kind=weekly&page=1&page_size=6`：完整周期归档，最多每页 20 条。
- `GET /api/digest/reports/{id}`：来源可追溯的历史报告。
- `GET /api/trends/hot-minerals?window=24h|48h|7d`。
- `GET /api/trends/price-alerts`、`price-trends`、`policy-updates`。

`/digest` 默认展示上一完整周期，可切换“本期实时简报”。`/trends` 和 `/digest` 均提供报告归档；归档链接带报告 ID，可分享、刷新和回退。

生成/回填报告，不向外部频道或收件人发送消息：

```powershell
cd "C:\Users\ltt18\Desktop\mineral resources advice\miningintel"
.\.venv\Scripts\python.exe -m pipeline.reporters.run_reports --kind daily
.\.venv\Scripts\python.exe -m pipeline.reporters.run_reports --kind monthly --as-of 2026-10-01
```

本地 PGlite 预览使用兼容包装器：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.pglite_runner --module pipeline.reporters.run_reports --kind daily
```

`--as-of` 表示以指定的**当地日期**为参照，生成此前完整周期，例如 2026-10-01 的 monthly 生成 2026-09-01 至 2026-10-01。CLI 会生成站内通知，外部通知由定时任务和显式启用的频道处理。

## 本地调度与部署

Redis、数据库、API 和前端需要保持运行。Windows 各开一个终端：

本机可选的 PGlite 预览使用 `run_preview_db.ps1`，只绑定 `127.0.0.1:55432`，允许 64 个连接，避免首页与报告并发超过旧的 10 连接上限。重启服务保留 `.tools/pglite/data`；生产仍使用 Compose 中的 PostgreSQL 16。

```powershell
.\run_worker.ps1 -InsightsOnly
.\run_scheduler.ps1 -InsightsOnly
```

此预览只执行报告/趋势/通知队列，不消费采集与 NLP 队列。完整运行去掉 `-InsightsOnly`；Windows 自动使用 solo 池。Linux Compose 的 worker 消费 `celery,nlp,insights`，Beat 只运行一个实例。趋势每 5 分钟刷新、通知调度每分钟恢复待处理任务。后台进程日志与调度文件位于 `artifacts/`。

## 通知与配置

邮件仅发送给活跃账户、开启邮件通知且匹配矿种/地区的订阅；每日/每周频率独立匹配。价格预警另需 `price_alerts_enabled=true` 主动开启。账户邮件由认证用户确定，不能替他人订阅。实际发送所需的是 SMTP 配置，不需要新的 LLM API Key。

SMTP SSL/STARTTLS 使用系统信任库验证服务器证书与主机名；本地 MailHog 配置关闭 TLS，作为仅用于回环地址的测试接收器。

```dotenv
EMAIL_NOTIFICATIONS_ENABLED=true
SMTP_HOST=your-smtp-host
SMTP_PORT=587
SMTP_USERNAME=your-smtp-account
SMTP_PASSWORD=your-smtp-password-or-app-password
SMTP_FROM=your-verified-sender
SMTP_STARTTLS=true
SMTP_SSL=false
PUBLIC_SITE_URL=https://your-miningintel-site
```

465 端口通常使用 `SMTP_SSL=true`、`SMTP_STARTTLS=false`。本地 MailHog 不需要认证：

```powershell
docker compose --env-file .env -f deploy/docker-compose.yml --profile mail up -d mailhog
```

本机 Python 服务设置 `SMTP_HOST=127.0.0.1`、`SMTP_PORT=1025`、`SMTP_FROM=miningintel@localhost`、`SMTP_STARTTLS=false`；Compose 内设置 `SMTP_HOST=mailhog`。MailHog 收件箱为 `http://127.0.0.1:8025`，不会把收到的邮件转发到外部。没有 Docker 的测试环境使用真实 loopback SMTP 接收器验证 Unicode 主题、正文、稳定 Message-ID 和一次性投递；测试在 `test_notification_transports.py`、`test_phase5_reports.py`，不是替换发送函数的 mock。

Webhook 配置默认关闭：

```dotenv
WEBHOOK_NOTIFICATIONS_ENABLED=false
SLACK_WEBHOOK_URL=
FEISHU_WEBHOOK_URL=
FEISHU_WEBHOOK_SECRET=
WECOM_WEBHOOK_URL=
```

启用后仅向配置的官方 HTTPS 机器人地址投递，不跟随重定向；URL 和签名密钥不进入 API 或日志。Slack 发送 text，飞书发送 msg_type/content，可选签名校验，企业微信发送 msgtype/text；除 HTTP 状态外还检查机器人业务返回码。429 延至下一调度周期再尝试，最多五次。格式依据 [Slack 文档](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/)、[飞书自定义机器人文档](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)、[企业微信机器人文档](https://developer.work.weixin.qq.com/document/path/91770)。本地测试实际发送到仅绑定 127.0.0.1 的测试 HTTP 服务。

报告、价格预警和每个频道投递都有唯一身份。网络 IO 前先持久化领取状态；发送成功保存时间。SMTP/网络结果不确定或 worker 领取后丢失时标记 `needs_review`，不会自动盲目重发；管理者核实收件情况后再处理。因 SMTP 自身没有事务性确认语义，不宣称跨服务 exactly-once。

`/notifications` 是消息中心。`GET /api/notifications`、`POST /api/notifications/{id}/read`、`POST /api/notifications/read-all` 均要求账户认证；响应 `Cache-Control: no-store`，已读记录按用户隔离，退出时客户端缓存清空。报告来源变动后通知也重新检查公开证据。

## 性能与验证

地图、矿种价格图、简报图、月报图均通过 `next/dynamic` 按路由加载。首页标题及原生搜索采用 Server Components，SSR 显示真实资讯，客户端加载后支持筛选与滚动；中文/英文标题通过 HTML 语言属性同步。首页先提供两篇完整文章，接近列表末尾自动取下一批，后续分页始终使用相同大小，避免切换批量大小导致漏读；其他页面保留各自的初始分页大小。

状态库合并为一个共享块，减少慢速网络下多批请求的等待；日期格式化与样式合并依赖分离。订阅入口使用轻量按钮，弹窗只在打开时下载，Framer Motion 在消息中心使用，首页卡片 hover 使用 CSS。桌面 Inter 使用两个独立缓存的本地静态子集，保留思源黑体子集；手机优先系统字体，避免下载字体阻塞阅读。屏幕外文章卡片、侧栏和页脚启用 content-visibility/尺寸占位。移除首页可见导航的自动预取，减少与首屏资源争抢。偏好初始化只在实际变化时更新语言/主题属性，避免重复排版。

复测结果见 `phase5-performance.json`；实际浏览器验证见 `phase5-browser-verification.json`，截图位于 `phase5-screenshots/`。性能记录使用生产 standalone、实际 API、Lighthouse 标准移动端模拟设置；本机测量不代表每一网络或设备都保证同样耗时。

2026-10-11 的交付验证：

- 手机首页两次性能均为 99 分，LCP 为 1962.72 / 1999.36 ms，中位数 1981.04 ms，TBT 和 CLS 均为 0；桌面性能 100 分、LCP 570.27 ms。可访问性与 SEO 均为 100 分。标准移动端节流配置完整保留在 JSON 中。
- 后端全套 151 项通过；新增“证据变更时重试”和“429 五次后停止自动重试”两项边界测试通过，相关定向套件共 20 项通过。Ruff、格式检查、TypeScript、生产构建与 3 项 SSE 测试通过。
- 真浏览器完成 14 篇实际资讯的无限滚动、筛选/排序与 URL 恢复、真实锂价图、真实地图瓦片、三个屏幕宽度、归档图表、账户登录/订阅/已读状态验证；没有 JavaScript 或 API 错误。PWA 离线与恢复测试通过，API 和私人 HTML 不进入 Service Worker 缓存。
- 三个真实报告通过 Celery 重复执行，ID 不变；报告与趋势调度器保持运行。Redis 热缓存命中耗时中位数 5.57–35.52 ms。任务与缓存的记录见 `phase5-scheduling-verification.json`。
- 修复本地预览连接上限后，16 路并发、3 轮清空公共缓存的 48 个请求全部返回 200，原有 20 篇文章、3 个归档报告与 3 条通知保留；记录见 `phase5-concurrency-verification.json`。
- 本地 SMTP 服务实际收到邮件；三个 Webhook 协议通过本地 HTTP 回执验证。外部邮件/机器人尚未开启，需要填写真实 SMTP/机器人配置后主动启用。

`scripts/phase5_live_verification.py` 可重新检查队列与缓存（要求外部通知关闭）；`scripts/record_phase5_performance.py --mobile <手机测量.json> [...] --desktop <桌面测量.json>` 会保留全部传入测量并校验手机目标。Lighthouse 在前端依赖中，可用 `node frontend/node_modules/lighthouse/cli/index.js http://127.0.0.1:3000/ --output=json --output-path=artifacts/mobile.json --chrome-flags="--headless=new"` 生成标准手机测量；桌面增加 `--preset=desktop`，Windows 设置 `CHROME_PATH` 为本机 Edge 路径。
