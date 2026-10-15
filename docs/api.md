# MiningIntel API · 阶段 3

## 账号专属选题推荐

所有 `/api/v1/topics/*` 接口要求有效的 Bearer JWT，仅访问本人选题与收藏；其他账号记录返回 404。响应使用 `Cache-Control: private, no-store`，不进入公开 Redis 缓存。网页入口为 `/topics`，公开前沿成果 `/frontier` 保持匿名可读。

- `GET /api/v1/topics/recommendations`：`type=achievement|social_science`（成果/社科；省略为全部）、`window=7d|30d|90d`（默认 30d）、`limit=1..50`（默认 20）、`bookmarked=true|false`。返回 `items/total/window/mode/message`。首次访问无记录时以规则生成并保存，不调用 LLM；无符合时间窗的已发布资料返回空数组、`mode=insufficient` 和“依据不足”。未知/未来发布日期不计入时间窗。
- `GET /api/v1/topics/{id}`：返回题目、摘要、逐条引用理由、矿种/地区/关键词、热度、生成方式、收藏状态及完整证据。证据包含 `evidence_type/entity_id/article_id/quote/quote_field/source_url/position/start_char/end_char/title/source_name/published_at`。原文位置为原始标题/正文中从零开始的字符区间 `[start_char,end_char)`，不是翻译文本位置。
- `POST /api/v1/topics/recommendations/refresh`：请求 `{"type":null,"window":"30d"}`。同步返回推荐页；至多一批十二个候选，LLM 调用限定 25 秒，只通过现有 `complete_json(system=..., prompt=...)` 网关。模型不可用、超时或结构校验失败时返回规则结果；假引用与对应理由一起剔除，剩余引用重新编号，全无效则回退规则。每账户串行生成，同时生成返回 409；刷新间隔至少一分钟，429 带 Retry-After。相同证据指纹复用选题 ID，保留收藏。
- `PUT /api/v1/topics/{id}/bookmark`、`DELETE /api/v1/topics/{id}/bookmark`：幂等收藏/取消，204。收藏保存在 PostgreSQL，GET 列表可筛选本人收藏。

热度是库内关注度评分（0–100），不是市场预测、论文影响因子或申报成功率。每批读取最近最多 240 篇已发布资料，以矿种、政策主题和研究方向聚合，7d 窗口复用既有热点分析器。事件证据使用该事件的已发布支持文章，政策证据须关联已发布同 URL 文章；不引用未审核的事件摘要。读取时重新核验原文摘录、URL、实体关联与发布状态，证据撤回/修改后整条旧推荐隐藏，避免展示失效理由。创新性和研究空白没有经过系统文献检索，明确标为依据不足。前端提供 Markdown 导出，仅包含服务端已核验内容。

数据库迁移为 `0010_topics`（继承 `0009_conversation_context`）。`topics` 按用户及证据指纹唯一，`topic_evidence` 保存原文定位，`topic_bookmarks` 按用户和选题唯一；删除账户级联删除本模块数据，不修改采集、问答、报告逻辑。

完整模型见运行中的 `/docs` 和 `/openapi.json`。网站读取基础路径为 `/api`；相同第三方读取接口挂载 `/api/open`，强制 `X-API-Key`。个人订阅、密钥管理和咨询需要 Bearer JWT，管理操作需要管理员。

## 文章、事件与聚合

- `GET /api/articles`：mineral、region、category、company、search、tag、date_from、date_to、page、page_size、sort_by。category=news/price/policy/report/company；sort_by=published_at/quality_score，降序，稳定排序。每页 1–100 条，返回 items/total/page/page_size。实体精确匹配，search 按字面子串检索。
- 日期接受 `2026-10-09` 或带时区时间戳：日期包含整个 UTC 日，时间戳使用 `[date_from,date_to)`。逆序范围返回 422。
- `GET /api/articles/{id}`：中英文正文与来源，未发布/撤回/不存在均 404。
- `GET /api/articles/hot`：近 48h Top 10，70% 质量 + 30% 新鲜度，排除未来文章，缓存 300 秒。
- `GET /api/articles/timeline?group_by=day|week`：同文章筛选，UTC 分组，最近最多 90 组，每组最多 5 条代表文章。
- `GET /api/events`：mineral、region、importance_score（最低分）、page、page_size。重要性降序，只用公开支持文章计算质量和数量。
- `GET /api/events/{id}`：代表摘要及最多 100 篇已发布关联文章。`/{id}/articles` 返回单独文章数组。
- `GET /api/minerals`：标准矿种、article_count、recent_count、previous_count、trend(up/down/flat)，比较最近 7 天与此前 7 天报道数，不代表价格涨跌。
- `GET /api/minerals/{name}/timeline`：group_by、date_from、date_to。
- `GET /api/minerals/{name}/prices`：date_from、date_to、source、price_type、limit。Numeric 序列化为字符串，保留 product、price_type、currency、unit、source、source_url。来源/币种/单位不同的序列分别绘图。
- `GET /api/minerals/{name}/policies`：region、page、page_size。
- `GET /api/regions`：地区计数及报道趋势；`GET /api/regions/{name}/articles` 返回地区分页文章，同文章筛选。
- `GET /api/policies`：region、mineral、date、page、page_size，date 为政策生效日期，只有支持文章已发布的政策可见。`/{id}` 返回详情。
- `GET /api/sources`：公开来源，不含采集配置/凭据；`GET /api/facets`：已发布矿种/地区/标签计数；`GET /api/prices`：全部价格，可选 mineral、limit。

## 趋势、简报、搜索

- `GET /api/trends/hot-minerals`：7 天报道量、前期数量、增长率。
- `GET /api/trends/price-alerts`：7 天同序列价格异动，默认绝对变化达到 5%，对比上一条报价，不默认相隔一天。
- `GET /api/trends/policy-updates`：30 天内发布的政策材料，区别于生效日。趋势缓存 1800 秒。
- `GET /api/digest/daily|weekly|monthly`：Asia/Shanghai 当前自然日、周一至下周一、月初至下月初，结束日不包含。stats 统计全周期公开文章，sources 选择最多 20 条证据。mode=empty/extractive/llm，缓存 3600 秒。GET 立即返回统计和摘录；Celery 生成逐句引用简报，来源哈希变化则退回最新摘录再生成。
- `GET /api/search?q=碳酸锂&limit=10`：articles/events/policies 和各类总计，limit 为每类上限 1–50，q 最长 200 字符。

缓存接口返回 `X-Cache: HIT|MISS|BYPASS`、`X-Cache-TTL`。公开数据提交后提升 Redis 版本，撤回立即失效。缓存错误可降级读库；启用 Redis 限流时其存储故障返回 503。

## 订阅与开放 API Key

先调用 `POST /api/v1/auth/register` 或 `/login`，请求 email/password，返回 access_token/user。个人接口携带 `Authorization: Bearer <token>`，角色不由请求参数控制。

`POST /api/subscriptions`：

```json
{"email":"analyst@example.com","subscribed_minerals":["锂","铜"],"subscribed_regions":["中国"],"frequency":"daily","email_enabled":false}
```

email 可省略，默认本人；frequency=daily/weekly。组内并集、矿种与地区之间交集，空组为全部。`GET /api/subscriptions/{email}` 查询，`DELETE` 删除。普通用户只能管理本人，否则 403。邮件要求用户选择接收且运营方配置 SMTP、开启 EMAIL_NOTIFICATIONS_ENABLED；只发送匹配且仍已发布的资料，唯一发送记录避免重复，不确定发送结果记为 needs_review。

`POST /api/api-keys` 请求 `{"name":"data-client","expires_in_days":90}`，key 仅返回一次，数据库保存 HMAC 摘要，每账户最多 10 个有效 Key，有效期 1–365 天。`GET /api/api-keys` 列元数据，`DELETE /api/api-keys/{id}` 撤销。第三方请求 `/api/open/articles` 等，携带 `X-API-Key: mi_...`。过期、撤销、用户停用立即失效。网站 `/api` 匿名可用，但传入无效 Key 会返回 401。

SlowAPI 默认每 IP、每路由每分钟 120 次，咨询/登录另有共享每分钟 10 次配额，429 返回 Retry-After。输入验证、绑定 SQL 参数和发布状态检查适用于所有公开路由。

## 咨询、管理、兼容

`POST /api/chat`、`POST /api/chat/stream`：question、session_id、minerals/regions 数组、category、start、end；返回 answer/sources/session_id/message_id/mode。SSE 为 status→sources→delta→done/error，仅 done 视为成功，历史保留最近 5 轮用于理解指代。`GET /api/chat/history/{session_id}`、`DELETE /api/chat/session/{session_id}` 验证所有者。API 时间戳保留 UTC，中文回答的参考来源日期按 Asia/Shanghai 显示。

管理保留 `/api/v1/admin/*`：信源 CRUD/触发采集、文章审核/重加工、任务状态、价格导入。未完成翻译的外文资料不能发布。旧 `/api/v1/*` 保留兼容，网站情报页面改用 `/api`；旧 `/api/v1/reports` 为历史归档，新 `/api/digest/*` 为当前自然周期。
