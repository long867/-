/** Product destinations, not search results or synthetic intelligence records. */
export const workspaceDestinations = [
  {
    href: "/",
    key: "home",
    group: "observe",
    zh: "情报中心",
    en: "Intelligence",
    note: "全球资讯与热点报道",
    noteEn: "Global coverage and developing stories",
  },
  {
    href: "/minerals",
    key: "minerals",
    group: "observe",
    zh: "矿产行情",
    en: "Mineral markets",
    note: "矿种目录、公开报价与产业链",
    noteEn: "Commodities, public prices and supply chains",
  },
  {
    href: "/regions",
    key: "regions",
    group: "observe",
    zh: "国家动向",
    en: "Country watch",
    note: "地区观察、项目与政策",
    noteEn: "Countries, projects and regional policy",
  },
  {
    href: "/policies",
    key: "policies",
    group: "observe",
    zh: "政策法规",
    en: "Policy library",
    note: "监管动态与原始文件",
    noteEn: "Regulation and original documents",
  },
  {
    href: "/trends",
    key: "trends",
    group: "observe",
    zh: "趋势洞察",
    en: "Market signals",
    note: "热点矿种、价格异动与变化",
    noteEn: "Coverage trends and price movements",
  },
  {
    href: "/events",
    key: "events",
    group: "observe",
    zh: "事件时间线",
    en: "Event timeline",
    note: "同一事件的多信源报道",
    noteEn: "Connected reporting across sources",
  },
  {
    href: "/digest",
    key: "digest",
    group: "research",
    zh: "情报简报",
    en: "Intelligence briefs",
    note: "日报、周报、月报与归档",
    noteEn: "Daily, weekly and monthly reports",
  },
  {
    href: "/frontier",
    key: "frontier",
    group: "research",
    zh: "前沿成果",
    en: "Research frontiers",
    note: "论文、研究方向与原始成果",
    noteEn: "Papers, research directions and findings",
  },
  {
    href: "/topics",
    key: "topics",
    group: "research",
    zh: "选题推荐",
    en: "Research topics",
    note: "有据可查的成果与社科选题",
    noteEn: "Evidence-backed applied and social research ideas",
  },
  {
    href: "/research",
    key: "research",
    group: "research",
    zh: "智能研判",
    en: "Decision research",
    note: "分析影响、情景与应对建议",
    noteEn: "Implications, scenarios and possible actions",
  },
  {
    href: "/chat",
    key: "chat",
    group: "research",
    zh: "矿眸智探",
    en: "矿眸智探",
    note: "结合资料对话、分析与追问",
    noteEn: "Consultation grounded in the evidence library",
  },
  {
    href: "/search",
    key: "search",
    group: "observe",
    zh: "全局检索",
    en: "Global search",
    note: "查找文章、事件和政策",
    noteEn: "Find articles, events and policies",
  },
  {
    href: "/bookmarks",
    key: "bookmarks",
    group: "personal",
    zh: "我的收藏",
    en: "Saved coverage",
    note: "继续阅读已收藏的情报",
    noteEn: "Return to your saved intelligence",
  },
  {
    href: "/subscriptions",
    key: "subscriptions",
    group: "personal",
    zh: "我的订阅",
    en: "Subscriptions",
    note: "关注矿种、地区与通知",
    noteEn: "Follow commodities and regions",
  },
  {
    href: "/notifications",
    key: "notifications",
    group: "personal",
    zh: "消息中心",
    en: "Notifications",
    note: "报告通知与价格预警",
    noteEn: "Report updates and price alerts",
  },
  {
    href: "/about",
    key: "about",
    group: "personal",
    zh: "关于平台",
    en: "About MiningIntel",
    note: "了解信源、数据与引用",
    noteEn: "Sources, methodology and citations",
  },
  {
    href: "/login",
    key: "login",
    group: "personal",
    zh: "账号登录",
    en: "Account",
    note: "进入你的专属研究工作台",
    noteEn: "Access your personal research workspace",
  },
  {
    href: "/admin",
    key: "admin",
    group: "manage",
    zh: "管理后台",
    en: "Administration",
    note: "信源、审核与任务监控",
    noteEn: "Sources, review and task monitoring",
  },
];

/** Resolve nested encoded routes without exposing opaque article/event IDs. */
export function workspaceLocation(pathname) {
  const segments = pathname.split(/[?#]/)[0].split("/").filter(Boolean);
  const key = segments[0] || "home";
  if (key === "articles")
    return {
      ...workspaceDestinations[0],
      detailZh: "文章详情",
      detailEn: "Article detail",
    };
  const destination =
    workspaceDestinations.find((item) => item.key === key) ||
    workspaceDestinations[0];
  if (!segments[1]) return { ...destination, detailZh: "", detailEn: "" };
  if (key === "minerals" || key === "regions") {
    let name = segments[1];
    try {
      name = decodeURIComponent(name);
    } catch {
      /* Keep malformed URLs readable. */
    }
    return { ...destination, detailZh: name, detailEn: name };
  }
  return {
    ...destination,
    detailZh: key === "events" ? "事件详情" : "详情",
    detailEn: "Detail",
  };
}

/** All query terms must match the destination; administrator routes stay gated. */
export function findDestinations(query, isAdmin = false) {
  const terms = query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  return workspaceDestinations.filter(
    (item) =>
      (isAdmin || item.group !== "manage") &&
      terms.every((term) =>
        `${item.zh} ${item.en} ${item.note} ${item.noteEn} ${item.key}`
          .toLocaleLowerCase()
          .includes(term),
      ),
  );
}

/** @param {string} key @returns {typeof workspaceDestinations} */
export function relatedDestinations(key) {
  const keys = {
    minerals: ["trends", "policies", "research"],
    regions: ["events", "policies", "trends"],
    policies: ["regions", "digest", "topics"],
    trends: ["minerals", "digest", "research"],
    digest: ["trends", "frontier", "research"],
    frontier: ["topics", "research", "digest"],
    topics: ["frontier", "research", "chat"],
    research: ["chat", "frontier", "trends"],
    chat: ["research", "frontier", "bookmarks"],
    events: ["regions", "trends", "digest"],
  }[key] || ["minerals", "frontier", "chat"];
  return keys
    .map((name) => workspaceDestinations.find((item) => item.key === name))
    .filter(Boolean);
}
