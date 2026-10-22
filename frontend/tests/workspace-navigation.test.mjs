import test from "node:test";
import assert from "node:assert/strict";
import {
  findDestinations,
  relatedDestinations,
  workspaceLocation,
} from "../lib/workspace-navigation.mjs";

test("breadcrumbs preserve encoded mineral/region names and hide opaque detail identifiers", () => {
  assert.equal(workspaceLocation("/minerals/%E9%94%82").detailZh, "锂");
  assert.equal(
    workspaceLocation("/regions/%E6%BE%B3%E5%A4%A7%E5%88%A9%E4%BA%9A").detailZh,
    "澳大利亚",
  );
  assert.equal(
    workspaceLocation("/articles/a-private-document-id").detailZh,
    "文章详情",
  );
  assert.equal(
    workspaceLocation("/events/a-private-event-id").detailZh,
    "事件详情",
  );
  assert.doesNotThrow(() => workspaceLocation("/minerals/%broken"));
});

test("destination search matches Chinese and English terms and does not expose administrator tools", () => {
  assert.ok(findDestinations("政策").some((item) => item.href === "/policies"));
  assert.ok(
    findDestinations("RESEARCH FRONTIERS").some(
      (item) => item.href === "/frontier",
    ),
  );
  assert.deepEqual(findDestinations("管理后台"), []);
  assert.equal(findDestinations("管理后台", true)[0].href, "/admin");
  assert.ok(
    relatedDestinations("minerals").every(
      (item) => item && item.href.startsWith("/"),
    ),
  );
});
