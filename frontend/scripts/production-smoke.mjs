/** Exercise the minified production entry on an isolated CI runner, without mocks. */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { cpSync, existsSync, mkdirSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";
// Already installed by the pinned Lighthouse development toolchain.
import puppeteer from "puppeteer-core";

const executablePath =
  process.env.CHROME_PATH ||
  [
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
  ].find(existsSync);
assert.ok(
  executablePath,
  "Set CHROME_PATH to an installed Chrome/Chromium browser",
);
const port = 3187;
const base = `http://127.0.0.1:${port}`;
let logs = "";
const standalone = path.resolve(".next/standalone");
assert.ok(
  existsSync(path.join(standalone, "server.js")),
  "Build the standalone production artifact first",
);
cpSync(".next/static", path.join(standalone, ".next/static"), {
  recursive: true,
});
cpSync("public", path.join(standalone, "public"), { recursive: true });
const server = spawn(process.execPath, [path.join(standalone, "server.js")], {
  cwd: standalone,
  env: {
    ...process.env,
    NODE_ENV: "production",
    NEXT_TELEMETRY_DISABLED: "1",
    PORT: String(port),
    HOSTNAME: "127.0.0.1",
  },
  stdio: ["ignore", "pipe", "pipe"],
});
for (const stream of [server.stdout, server.stderr])
  stream.on("data", (data) => {
    logs = (logs + data).slice(-6000);
  });
let browser;
let page;
const errors = [];
try {
  let ready = false;
  for (let attempt = 0; attempt < 60; attempt++) {
    if (server.exitCode !== null)
      throw new Error(`Production server exited: ${server.exitCode}`);
    try {
      ready = (await fetch(base, { signal: AbortSignal.timeout(5000) })).ok;
    } catch {
      /* Wait for startup. */
    }
    if (ready) break;
    await delay(500);
  }
  assert.ok(ready, "Production server did not become ready");
  browser = await puppeteer.launch({
    executablePath,
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1050 });
  page.on("pageerror", (error) => errors.push(String(error.stack || error)));
  page.on("console", (message) => {
    if (
      message.type() === "error" &&
      message.text().includes("[MiningIntel visual]")
    )
      errors.push(message.text());
  });
  page.on("requestfailed", (request) => {
    if (request.url().includes("/_next/"))
      errors.push(`Asset network failure: ${new URL(request.url()).pathname}`);
  });
  page.on("response", (response) => {
    if (response.url().includes("/_next/") && response.status() >= 400)
      errors.push(
        `Asset HTTP ${response.status()}: ${new URL(response.url()).pathname}`,
      );
  });
  assert.equal(
    (
      await page.goto(base, { waitUntil: "networkidle0", timeout: 90000 })
    ).status(),
    200,
  );
  await page.waitForSelector(".field-stage", { timeout: 20000 });
  await page.evaluate(() =>
    [...document.querySelectorAll(".observatory-mode-bar button")]
      .find((button) => button.textContent.includes("全球地球"))
      .click(),
  );
  await page.waitForSelector('.resource-globe[data-ready="true"]', {
    timeout: 25000,
  });
  await page.evaluate(() =>
    [...document.querySelectorAll(".observatory-mode-bar button")]
      .find((button) => button.textContent.includes("资源星图"))
      .click(),
  );
  await page.waitForSelector(".field-stage");
  await page.click(".field-expand");
  await page.waitForSelector(".field-dialog .field-stage");
  await page.keyboard.press("Escape");
  for (let attempt = 0; attempt < 3; attempt++) {
    assert.equal(
      (
        await page.goto(base, { waitUntil: "networkidle0", timeout: 60000 })
      ).status(),
      200,
    );
  }
  assert.deepEqual(
    errors,
    [],
    "Production browser exceptions or failed assets",
  );
  console.log(
    "Production constellation/globe switching, expansion and repeated homepage loads passed",
  );
} catch (error) {
  if (page) {
    const directory = path.join(
      process.env.RUNNER_TEMP || os.tmpdir(),
      "miningintel-production-smoke",
    );
    mkdirSync(directory, { recursive: true });
    await page
      .screenshot({ path: path.join(directory, "failure.png") })
      .catch(() => {});
  }
  console.error(logs);
  console.error("Production browser errors:", JSON.stringify(errors));
  throw error;
} finally {
  if (browser) await browser.close();
  server.kill("SIGTERM");
}
