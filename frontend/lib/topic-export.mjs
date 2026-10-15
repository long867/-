/** Export only the server-verified proposal and its original evidence. */
/** @param {import("../types").Topic} topic */
export function topicMarkdown(topic) {
  const type = topic.type === "achievement" ? "成果选题" : "社科选题";
  return [
    `# ${topic.title_zh || topic.title}`,
    "",
    `类型：${type} · 关注度：${topic.heat_score}/100 · 时间窗：${topic.window}`,
    `生成时间：${topic.generated_at}`,
    `生成方式：${topic.mode === "llm" ? "AI 辅助（引用已核验）" : "规则推荐"}`,
    "",
    "## 推荐摘要",
    "",
    topic.summary,
    "",
    "## 推荐理由与研究建议",
    "",
    topic.rationale,
    "",
    "## 原文证据",
    "",
    ...topic.evidence.flatMap((e) => [
      `### [${e.position}] ${e.title}`,
      `来源：${e.source_name} · 日期：${e.published_at || "未知"}`,
      `链接：${e.source_url}`,
      `库内类型：${e.evidence_type} · 记录：${e.entity_id} · 支持文章：${e.article_id}`,
      `摘录位置：${e.quote_field} 字符 [${e.start_char}, ${e.end_char})`,
      "",
      ...e.quote.split(/\r?\n/).map((line) => `> ${line}`),
      "",
      `研究建议（待验证）：${e.support}`,
      "",
    ]),
    "## 依据边界",
    "",
    topic.limitation,
    "",
  ].join("\n");
}
