# 阶段 4：真实数据前端工作台

前端采用 Next.js 14 App Router、TypeScript、Tailwind、Radix/shadcn 风格组件、TanStack Query、Recharts、Leaflet 与 Framer Motion。深蓝与铜金配色支持明暗切换；界面支持中文/英文，原文和已有中文译文分别展示。

## 启动与查看

本机已使用项目 Python、PGlite 55432、WSL Redis 6380 和实际采集的资料。API 运行在 8001，网站运行在 3000。

```powershell
cd "C:\Users\ltt18\Desktop\mineral resources advice\miningintel"
# 终端一；保持运行
.\run_api.ps1
# 终端二；第一次或修改代码后先构建
cd frontend
npm ci
npm run build
cd ..
.\run_web.ps1 -Production
```

打开 [网站](http://127.0.0.1:3000/) 与 [API 文档](http://127.0.0.1:3000/api-docs)。开发模式使用 `.\run_web.ps1`。脚本会识别并复用已有服务；切换模式前，在原服务终端按 Ctrl+C。构建前应停止开发服务，避免两个 Next 进程共用 `.next`。

全新机器使用 README 的 PostgreSQL 16 / Redis / Docker 配置。本地兼容适配器仅用于已核实的 PGlite，不能代替生产 PostgreSQL。管理员账号按 README 的 `python -m app.cli create-admin 邮箱` 命令配置；本机 PGlite 使用 `.\.venv\Scripts\python.exe -m scripts.pglite_runner --module app.cli create-admin 邮箱`，密码交互输入。普通用户不能访问后台。

## 页面与数据

- `/`：48 小时热点、真实卡片流、按天时间线、矿种/地区/主题多选、排序与日期筛选、热门矿种、最新政策、价格异动。
- `/minerals`、`/minerals/[name]`：矿种目录、真实价格曲线、资讯、相关政策与公司。
- `/regions`、`/regions/[name]`：地区目录、地图、项目报道和政策。项目标记只接受信源元数据中合法的经纬度；现有文章未披露坐标的项目显示报道入口，不生成虚构矿山位置。
- `/policies`：地区、矿种、生效日期范围筛选，卡片/时间线与分页。
- `/trends`：真实报道数量与前期增长、价格异动、政策动态、周报和月报入口。
- `/digest`：日/周/月切换、带引用的摘要、统计图和重点文章。
- `/search`：文章/事件/政策搜索、结果数量、文本高亮、矿种/地区/日期筛选与分页。文章类别筛选仅作用于文章；政策按生效日期筛选。
- `/articles/[id]`、`/events/[id]`：原文、译文、标签、关联资料与来源入口。文章详情使用无缓存服务端请求，并由客户端复核发布状态。
- `/chat`：真实 SSE、检索/生成状态、追问提示、历史会话、可点击来源编号与原文片段。
- `/admin`：权限保护的信源新增/编辑/停用/删除、采集任务提交、审核/撤回、文章标签编辑、运行记录和 Celery 状态查询。
- `/bookmarks`、`/subscriptions`：本机收藏与登录账号订阅，另有全站订阅弹窗。

同一筛选组内取并集，矿种、地区、主题组之间取交集。筛选条件与视图同步到 URL；无限滚动按页获取，交叉观察器与手动加载共同支持，按文章 ID 去重。数据库是所有文章、行情、政策、项目和统计的来源，没有运行时 mock。空结果、处理中、请求失败分别展示。

## 数据获取与性能

首页及目录使用 Server Components 注入实际首屏资料，公共数据通过 ISR 每 300 秒更新。后端不可用时不填充样例内容，客户端查询恢复真实数据。TanStack Query 管理筛选、分页、会话和变更后的刷新；登录令牌只保留在内存，退出时清除查询缓存。

图表和地图动态加载，首页不加载 Recharts / Leaflet。Framer Motion 使用 LazyMotion。字体自托管：Inter 拉丁可变字体、思源黑体系列 Noto Sans SC 的界面子集与独立标题子集；未覆盖的正文字符使用系统中文字体。所有字库附 SIL OFL 授权文件。预生成资产已入仓，构建无需 Python 字体工具；改动界面文字后可安装 `fonttools`、`brotli` 并运行 `python scripts/subset_ui_fonts.py` 再构建。

PWA 提供 manifest、192/512 图标与服务工作线程。缓存只包含静态代码资产与离线提示页，不保存 API 返回值、登录页或私人会话 HTML；断网时显示离线说明，避免把旧行情当作最新报价。

底图使用 OpenStreetMap 标准瓦片，保留可见署名，沿用浏览器缓存与 Referer，不预抓取或提供离线地图。可通过前端构建环境变量 `NEXT_PUBLIC_MAP_TILE_URL` 更换瓦片服务；上线流量增加时按 [OSM 瓦片政策](https://operations.osmfoundation.org/policies/tiles/) 使用适合部署规模的底图服务。

## 验证

2026-10-11 本机生产构建通过，首页全部来自 14 篇已发布真实文章和 39 个信源配置。没有使用拦截接口或合成新闻进行以下浏览器验收。

- `npm run typecheck`、`npm test`（3 项 SSE 测试）、`npm run build` 通过。
- 后端全量 129 项测试通过；新增信源地址冲突/编辑/删除检查后，最新业务 API 专项 10 项通过。Ruff 全项目检查及格式检查通过。
- `scripts/frontend_live_smoke.py`：真实资讯无限滚动、URL 多选与刷新、搜索高亮、详情、收藏、明暗/语言持久化、价格图、地图与真实底图、周报图、订阅弹窗及 390/768/1440 像素适配通过，JS 与 API 错误为 0。
- `scripts.admin_browser_live_smoke.py`：真实后台新增/编辑/停用/删除、四个模块、任务状态、订阅保存通过；临时账号与信源在 finally 中删除。
- `scripts.rag_browser_live_smoke.py`：登录、真实 SSE、天气问题资料不足、锂价原文引用跳转、多轮追问与删除会话通过；临时账号自动删除。
- `scripts.pwa_live_smoke.py`：图标、manifest、服务工作线程、缓存边界、离线与恢复联网通过。

性能报告与截图保存在 `artifacts/`，关键指标另保存为 [phase4-performance.json](phase4-performance.json)。Lighthouse 分别使用移动端默认模拟和桌面预设；这是本机生产构建的测量，线上延迟还取决于部署与网络。桌面性能/可访问性/最佳实践/SEO 均为 100，FCP 0.35 秒、LCP 0.74 秒；移动端性能 92，其余三项 100，FCP 1.37 秒、LCP 3.32 秒，CLS 为 0。首屏显示达 2 秒以内，移动端慢网模拟的最大内容绘制仍高于 2 秒，不将桌面成绩描述成全球网络保证。

