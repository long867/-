import test from "node:test";
import assert from "node:assert/strict";
import { researchCitation, researchRis } from "../lib/research-export.mjs";

const paper = {
  title: "Copper recovery",
  title_zh: "铜回收研究",
  journal: "Test journal",
  authors: ["Ada Example", "Bo Example"],
  published_date: "2026-10",
  doi: "10.5555/test",
  url: "https://doi.org/10.5555/test",
};

test("research exports preserve original title, authors and exact DOI without invented bibliographic fields", () => {
  const ris = researchRis([paper]);
  assert.match(ris, /TI  - Copper recovery\r\n/);
  assert.match(ris, /AU  - Ada Example\r\nAU  - Bo Example/);
  assert.match(ris, /PY  - 2026/);
  assert.match(ris, /DO  - 10\.5555\/test/);
  assert.doesNotMatch(ris, /VL  -|SP  -|AB  -|DA  -/);
  assert.match(researchCitation(paper), /Test journal\. 2026\. DOI:/);
});

test("exported metadata cannot inject extra RIS records with embedded newlines", () => {
  const ris = researchRis([{ ...paper, title: "Title\r\nTY  - ELEC" }, paper]);
  assert.equal(
    ris.split("\r\n").filter((line) => line.startsWith("TY  - ")).length,
    2,
  );
  assert.equal(
    ris.split("\r\n").filter((line) => line.startsWith("ER  - ")).length,
    2,
  );
});
