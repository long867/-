import test from "node:test";
import assert from "node:assert/strict";
import { resourceNodes, resourcePreview } from "../lib/resource-field.mjs";

test("constellation retains exact source counts without summing duplicate facets", () => {
  const facets = [
    { name: "铜", count: 14 },
    { name: "金", count: 20 },
    { name: "铜", count: 12 },
    { name: "未知", count: 0 },
    { name: "", count: 40 },
    { name: "锂", count: NaN },
  ];
  const result = resourceNodes(facets);
  assert.deepEqual(
    result.map(({ name, count }) => ({ name, count })),
    [
      { name: "金", count: 20 },
      { name: "铜", count: 14 },
    ],
  );
  assert.equal(facets.length, 6);
  assert.ok(
    result.every(
      (node) => node.x >= 70 && node.x <= 530 && node.y >= 60 && node.y <= 400,
    ),
  );
});

test("visual complexity stays bounded with a large real catalog", () => {
  const result = resourceNodes(
    Array.from({ length: 1000 }, (_, index) => ({
      name: `矿种${index}`,
      count: index + 1,
    })),
    1000,
  );
  assert.equal(result.length, 8);
  assert.equal(result[0].count, 1000);
  assert.deepEqual(resourceNodes(), []);
});

test("preview uses exact published tags, rejects drafts and deduplicates sources", () => {
  const articles = [
    { id: "a", status: "published", minerals: ["铁矿石"], regions: ["中国"] },
    { id: "b", status: "pending", minerals: ["铁"], regions: ["中国"] },
    { id: "c", status: "published", minerals: ["铁"], regions: ["澳大利亚"] },
    { id: "c", status: "published", minerals: ["铁"], regions: ["澳大利亚"] },
  ];
  assert.deepEqual(
    resourcePreview(articles, "minerals", "铁").map(({ id }) => id),
    ["c"],
  );
  assert.deepEqual(
    resourcePreview(articles, "regions", "中国").map(({ id }) => id),
    ["a"],
  );
  assert.deepEqual(resourcePreview(articles, "minerals", undefined), []);
});
