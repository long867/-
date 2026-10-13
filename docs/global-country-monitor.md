# 全球国家资源动向

入口：`/regions`，国家详情：`/regions/{中文国家名}`。

- 目录来自联合国统计司 [M49 国家与地区表](https://unstats.un.org/unsd/methodology/m49/overview/)，249 个国家与地区，另列欧盟；不是宣称已接入 250 个国家的实时政府数据。
- 看板区分近期报道、历史资料、暂无资料，按洲、矿种、主题和 7 / 30 天窗口筛选。累计与窗口计数只读取已发布资料，排除虚构种子、未来日期和价格快照。
- 观察主题：政策与监管、出口与贸易、矿山与勘探、供应链与生产、投资与交易。规则匹配标题和摘要，显示报道线索及其原始链接，不将提案、新闻报道或关键词计数当作生效法规、预警等级或国家风险分数。
- 政策文件数量来自 `policies` 表且关联已发布原文，和政策新闻线索分开。
- 国家地图点是地区中心；矿山项目地图仍只使用信源提供的真实坐标。
- 每 30 分钟调度器检查到期信源，新接入公开 RSS 每 6 小时采集一次，遵守 robots、条件请求、退避、去重和中文摘要审核。看板缓存及前端查询每 5 分钟刷新。
- 国家页可把国家背景和分析问题带入“矿眸智探”，沿用事实引用与推论分离、多轮记忆。新增国家名称在采集、检索和会话记忆共用同一词表。

## API

- `GET /api/regions/monitor?days=7&mineral=铜&topic=trade`：全部目录及实际覆盖，支持 `days=7|30`，`topic=policy|trade|projects|supply_chain|investment`。
- `GET /api/regions/{name}/intelligence`：该国家统计与最新文章。
- `GET /api/articles?region=马拉维&topic=projects&exclude_prices=true`：主题资讯流，可继续分页、排序、筛选。

响应说明包含统计时间、最近成功采集时间与来源；响应缓存由正常入库自动失效。

## 维护

更新 M49 目录：`python scripts/update_country_catalog.py`。保留现有中文规范名，补充六种联合国语言名称，排除 Jordan、Chad、Georgia、Santa Elena、Reunión 等人物、州名、矿山名或普通词歧义。

已有语料地区重识别：先 `python -m pipeline.refresh_country_tags --dry-run`，再 `python -m pipeline.refresh_country_tags`。每批 50 篇，仅改地区元数据及事件地区；不改原文、引用片段或偏移。价格来源保持原有明确地域。更新完成后清除公共缓存。

小规格服务器继续使用轻量词表和公开每日报价；不新增大模型、地图服务或独立长期容器。受限、付费、空响应或未验证信源不自动启用。
