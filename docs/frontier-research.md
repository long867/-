# 前沿成果

公开入口 `/frontier`，API 为 `GET /api/frontier` 与 `GET /api/frontier/{id}`。
访客无需登录即可查看中文题名、摘要、研究方向、矿种、作者、机构、期刊、发布日期与 DOI。
支持方向、矿种、时间窗口、主题/作者/期刊/DOI 搜索和分页，筛选同步 URL。

首批通过 Crossref 公共 REST API 追踪 Minerals、Ore Geology Reviews、Minerals Engineering、
Hydrometallurgy、Resources Policy、International Journal of Mining Science and Technology、
Metals、Resources，共8本期刊。后两本增加公开摘要覆盖，宽主题期刊会再过滤矿产资源相关内容。
来源存放于 `pipeline/config/sources.yaml` 的 `frontier_research` 组；新版本发布时注册信源，
现有每30分钟调度器按信源 `fetch_interval=86400` 执行每日增量采集。
每次每刊最多24条，首批最多192条，最近一年，先采集再独立中文加工；
重复 DOI 统一小写 URL，沿用数据库唯一约束。这个有界窗口不等于完整收录全球全部论文。
来源开关由管理员控制，发布与目录同步保留已修改的开关。

成果复用 articles、审核、原文分块和检索索引，`raw_json.document_kind=research_paper`
区分学术论文与新闻/研报；没有另建重复语料库。公开查询仅返回已发布、非未来日期论文。
作者、机构、研究主题取自题录与规则，不将作者所属国家直接当作研究对象所在地。
发布日期优先在线发表日期，月/年精度不在页面伪装成精确到日；采集时间另列。

有公开摘要才提炼研究方法与结果；没有摘要只翻译题名并标注“题录速览”，
不虚构研究结论、不绕过付费全文。中文加工校验数字与单位，实验结果不表述为已经产业化。
中文题名同时校验矿种与 Co/Ni/Cu 等明确元素名称，避免把钴等术语译错。
长摘要选取完整的问题、方法和主要结果句，不把半句话截断成新的研究结论。
学术记录质量按权威性40%、DOI20%、日期10%、作者10%、期刊10%、摘要10%评分；
新旧由发表日期排序和时间筛选体现，不将新闻的短时效衰减作为论文题录完整性评分。
Crossref 不保证摘要覆盖，也不能仅凭 journal-article 类型断言同行评议已经确认。
阅读工具包括卡片/列表视图、收藏、复制原文文献引用和本页 RIS 题录导出。
导出仅包含实际提供的题录字段，不编造卷期、页码，也不把平台摘要伪装成作者原始摘要。

后续“选题推荐”作为独立的登录功能：按账号保存研究兴趣、研究成果选题与社科选题，
生成理由、依据与待验证问题；所有推荐和历史按服务端认证 user_id 隔离。
本次先上线公开前沿成果，不把“研判”历史改造成公开推荐，也不展示未实现的推荐按钮。

参考：[Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)、
[公开访问与限速](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/)。
