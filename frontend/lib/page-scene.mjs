/** Route-specific decorative motifs never represent measured research/price data. */
export function pageScene(pathname) {
  const segment = pathname.split("/").filter(Boolean)[0] || "home";
  const scenes = {
    home: "observatory",
    minerals: "crystal",
    regions: "atlas",
    policies: "policy",
    trends: "signals",
    digest: "brief",
    research: "reasoning",
    frontier: "discovery",
    topics: "discovery",
    chat: "reasoning",
    search: "radar",
    articles: "brief",
    events: "signals",
    admin: "operations",
    notifications: "radar",
    subscriptions: "network",
    bookmarks: "brief",
    login: "network",
    about: "observatory",
  };
  return scenes[segment] || "observatory";
}

export const sceneCardSelector = [
  ".article-card",
  ".policy-card",
  ".directory-card",
  ".event-card",
  ".metric-card",
  ".market-card",
  ".country-card",
  ".frontier-paper",
  ".topic-card",
  ".hot-card",
  ".observatory-card",
  ".notification-item",
  ".form-card",
  ".panel",
  ".chat-intro",
  ".country-observatory",
  ".frontier-hero",
  ".topic-hero",
  ".market-summary",
  ".page-heading",
  ".message",
  ".chat-source",
  ".topic-evidence",
  ".research-source",
].join(",");
