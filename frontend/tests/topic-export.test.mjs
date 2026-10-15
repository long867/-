import assert from "node:assert/strict";
import test from "node:test";
import { topicMarkdown } from "../lib/topic-export.mjs";

test("topic export retains exact evidence, citation numbering and known-date boundary", () => {
  const result = topicMarkdown({
    title: "铜回收研究",
    type: "achievement",
    heat_score: 50,
    window: "30d",
    generated_at: "2026-10-15T00:00:00Z",
    mode: "rule",
    summary: "待验证的研究设想",
    rationale: "原文支持该研究主题 [1]",
    limitation: "创新性依据不足",
    evidence: [
      {
        position: 1,
        title: "原文题目",
        source_name: "测试来源",
        published_at: null,
        source_url: "https://example.com/fixture",
        evidence_type: "article",
        entity_id: "a",
        article_id: "a",
        quote_field: "content",
        start_char: 4,
        end_char: 12,
        quote: "Original\nquotation",
        support: "可开展进一步核验",
      },
    ],
  });
  assert.ok(result.includes("[1]"));
  assert.ok(result.includes("> Original\n> quotation"));
  assert.ok(result.includes("字符 [4, 12)"));
  assert.ok(result.includes("日期：未知"));
  assert.ok(result.includes("创新性依据不足"));
  assert.ok(!result.includes("undefined"));
});
