/** Export the displayed brief and its actual evidence without adding analysis. */
/** @param {import("../types").Digest} digest */
export function digestMarkdown(digest) {
  return [
    `# ${digest.title}`,
    "",
    `周期：${digest.period_start} — ${digest.period_end}（结束日不含） · ${digest.timezone}`,
    `收录 ${digest.stats.article_count} 篇已发布资料 · ${digest.stats.source_count} 个信源`,
    "",
    digest.content,
    "",
    "## 原始资料",
    "",
    ...digest.sources.map((source, index) =>
      [
        `### [${index + 1}] ${source.title.replace(/[\r\n]+/g, " ")}`,
        `来源：${source.source_name}`,
        `发布时间：${source.published_at || "未披露"}`,
        source.snippet,
        source.url,
        "",
      ].join("\n"),
    ),
    "",
    "MiningIntel · 矿眸智探",
  ].join("\n");
}
