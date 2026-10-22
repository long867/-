import test from "node:test";
import assert from "node:assert/strict";
import { digestMarkdown } from "../lib/digest-export.mjs";

test("brief export preserves evidence, unknown dates and the selected period", () => {
  const result = digestMarkdown({
    title: "本期简报",
    kind: "daily",
    period_start: "2026-10-22",
    period_end: "2026-10-23",
    timezone: "Asia/Shanghai",
    stats: { article_count: 1, source_count: 1 },
    content: "已有资料摘要 [1]",
    sources: [
      {
        title: "原始题目",
        source_name: "原始信源",
        published_at: null,
        snippet: "可核验摘录",
        url: "https://example.org/evidence",
      },
    ],
  });
  assert.match(result, /2026-10-22 — 2026-10-23/);
  assert.match(result, /发布时间：未披露/);
  assert.match(result, /已有资料摘要 \[1\]/);
  assert.match(result, /可核验摘录\nhttps:\/\/example.org\/evidence/);
  assert.doesNotMatch(result, /预计|预测|2026-10-22T/);
});
