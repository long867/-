import test from "node:test";
import assert from "node:assert/strict";
import {
  normalizeWatchlist,
  latestQuotation,
  observationItems,
} from "../lib/observation.mjs";

test("watchlist storage rejects malformed values, deduplicates and caps the list", () => {
  assert.deepEqual(normalizeWatchlist({ names: ["锂"] }), []);
  assert.deepEqual(
    normalizeWatchlist(["锂", null, "", "铜", "锂", " 铜 ", "<bad>", 42]),
    ["锂", "铜"],
  );
  assert.equal(
    normalizeWatchlist(Array.from({ length: 20 }, (_, i) => `矿种${i}`)).length,
    12,
  );
});

test("latest quotation rejects absent values and keeps the actual dated product and units", () => {
  const actual = {
    id: "real",
    date: "2026-10-20",
    price: "92000",
    product: "碳酸锂",
    currency: "CNY",
    unit: "吨",
  };
  const values = [
    { id: "null", date: "2026-10-22", price: null },
    { id: "blank", date: "2026-10-22", price: "" },
    { id: "invalid", date: "unknown", price: "98000" },
    { id: "earlier", date: "2026-10-19", price: "90000" },
    actual,
  ];
  assert.equal(latestQuotation(values), actual);
  assert.equal(values[0].id, "null");
  assert.equal(latestQuotation([{ date: "2026-10-22", price: "NaN" }]), null);
});

test("personal observations preserve user order and unquoted entries without synthesizing prices", () => {
  const copper = {
    name: "铜",
    prices: [{ price: "70000", date: "2026-10-21" }],
  };
  const graphite = { name: "石墨", prices: [] };
  const lithium = {
    name: "锂",
    prices: [{ price: "90000", date: "2026-10-20" }],
  };
  assert.deepEqual(
    observationItems([copper, graphite, lithium], ["石墨", "锂", "不在目录中"]),
    [graphite, lithium],
  );
  assert.deepEqual(observationItems([graphite, copper, lithium], []), [
    copper,
    lithium,
  ]);
});
