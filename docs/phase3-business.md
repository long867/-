# 阶段 3：后端业务与真实数据

情报业务拆分为 article/event/trend/digest/subscription 服务和 9 类 API 路由。网站读取 `/api`，第三方读取 `/api/open` 强制 API Key；个人操作使用 JWT 与所有权校验。参数和响应见 [API 文档](api.md)，完整 OpenAPI 由代码生成。

## 翻译与真实资料

已清理开发期已知演示 URL 前缀下的文章、信源、价格和政策，保留真实原文及用户。`scripts/remove_demo_data.py` 默认预览，显式 --apply 才清理，生产环境拒绝执行。首页只展示已发布的真实入库资料。

模型只缺少中文摘要字段且标题已合格时，完整正文翻译通过校验后可提取 100–200 字的完整开头句，明确标为“【译文摘录】”。正文或数字校验失败仍保持 pending，不把摘录冒充模型综合分析。

数字以 Decimal 规范化比较，允许原文明示的数量词忠实转写。百分比、币种、数量级、单位和完整英文日期通过可逆锚点保护。模型漏值、重复或改值时重试/细分，不合格保留 pending。分段优先完整句，避免长宽数量在句中被截断；模型 answer/result 对象外壳规范化后继续校验。原文自身矛盾的数值保留，不擅自纠正；校验不能代替专业审稿。

## 锂价采集

sources.yaml 新增“生意社碳酸锂公开现货价格”，使用公开现货/期货对照表。正常浏览器加载 JavaScript 页面，遵循 robots。必须具有报价日期、唯一现货行和“元/吨”单位说明，缺值/未来日期/歧义/单位变化会失败，不把期货列当现货。

```powershell
.\run_pipeline.ps1 --source '生意社碳酸锂公开现货价格' --dry-run
.\run_pipeline.ps1 --source '生意社碳酸锂公开现货价格'
```

2026-10-11 实测入库 2026-09-18 至 2026-10-09 的 10 条报价，最新 121000.00 CNY/吨。来源未注明等级，product 为“碳酸锂（生意社现期表现货口径）”，不能称电池级或锂矿石价格。source 保存稳定序列，source_url 指向实际抓取页，最新记录可能来自滚动首页；raw_json 保存当时的表行和日期精度。文章使用稳定的日期页面 URL。中文价格使用确定性摘要；英文仍使用 LLM。重复采集 fetched=10、duplicates=10、new=0、errors=0。

价格检索同时支持连续行情文字和经过校验的结构化表格。数值与单位说明分行时，两者都必须存在于引用片段，价格元数据必须完整。回答校验使用原文片段和已审核标题中的数字/币种/单位证据，保留逐字引用，避免将表中的期货列混作现货报价。

## 缓存、简报与邮件

热点缓存 300 秒、趋势 1800 秒、日/周/月报 3600 秒，数据提交后提升共享缓存版本。撤回立即失效。缓存失败可降级读库；生产 Redis 限流存储失败返回 503。

SlowAPI 通过全局 FastAPI 依赖执行，避免新版 FastAPI 懒加载嵌套路由被旧 SlowAPI 中间件跳过。每 IP、HTTP 方法、路由模板共享配额，改变文章 ID 或调用开放 API 别名不能绕过同类配额。登录/问答另有每分钟 10 次配额。

简报按 Asia/Shanghai 自然日/周/月和 published_at 统计。GET 返回统计及证据摘录；Celery 每 15 分钟检查新增证据，在数据库事务外调用模型，保存前重新核对证据哈希。事实逐句引用，原文片段和数值必须可验证；空周期明确显示暂无资料。

后台任务 miningintel.generate_brief 参数 daily/weekly/monthly。SMTP 需 EMAIL_NOTIFICATIONS_ENABLED、SMTP_HOST/PORT/FROM 等设置，用户 email_enabled 为 true 才发送。每用户/简报唯一发送记录，不确定结果留待核对，避免重复外发。本次未启用真实邮件发送。

迁移 0004_business_api 添加发布时间/质量/公司 GIN/事件重要性索引和价格溯源、邮件偏好、报告证据哈希、个人 API Key、通知记录。既有矿种/地区 GIN 索引保留。Key 保存 HMAC SHA-256，账户行锁限制有效 Key 数量。

## 启动与部署

项目根目录 .env 读取本地配置，修改后重启 API/worker。run_api.ps1/run_web.ps1 使用 8001/3000，识别已运行 MiningIntel，不自动终止占用端口的其他服务。PGlite 只作本机兼容环境，生产使用 PostgreSQL 16。

```powershell
.\run_api.ps1
.\run_web.ps1
# Docker Desktop 可用时
docker compose --env-file .env -f deploy/docker-compose.yml up --build -d
```

Compose 覆盖容器的数据库、Redis、模型缓存、浏览器配置，避免沿用 Windows 路径/本机端口。POSTGRES_PASSWORD 应使用可直接放入 URI 的字符，或自行 URL 编码数据库连接配置。CI 使用独立 PostgreSQL 16、Redis、Qdrant 执行测试和迁移。本机性能测量的环境与范围见 [验证记录](phase3-verification.md)。
