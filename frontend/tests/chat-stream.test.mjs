/** SSE protocol checks with synthetic responses; no external model is called. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

const source = await readFile(
  new URL("../lib/chat-stream.ts", import.meta.url),
  "utf8",
);
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ES2022,
  },
});
const { parseFrame, streamChat } = await import(
  `data:text/javascript;charset=utf-8,${encodeURIComponent(compiled.outputText)}`
);

const completed = {
  session_id: "test-session",
  message_id: "test-message",
  answer: "中文测试。 [1]",
  sources: [],
  mode: "extractive",
};
function frame(event, data) {
  return `event: ${event}\r\ndata: ${JSON.stringify(data)}\r\n\r\n`;
}
function mockResponse(body) {
  const bytes = new TextEncoder().encode(body);
  return new Response(
    new ReadableStream({
      start(controller) {
        // Split each multibyte Chinese character and CRLF boundary across reads.
        for (const byte of bytes) controller.enqueue(Uint8Array.of(byte));
        controller.close();
      },
    }),
    { headers: { "Content-Type": "text/event-stream" } },
  );
}

test("fragmented UTF-8 and multiple SSE frames produce one complete answer", async (t) => {
  t.mock.method(globalThis, "fetch", async (_url, init) => {
    assert.equal(init.method, "POST");
    assert.equal(init.headers.Authorization, "Bearer fixture-token");
    assert.equal(JSON.parse(init.body).session_id, "existing-session");
    return mockResponse(
      ": heartbeat\r\n\r\n" +
        frame("status", { phase: "retrieving" }) +
        frame("sources", { sources: [] }) +
        frame("delta", { text: "中文测试。 " }) +
        frame("delta", { text: "[1]" }) +
        frame("done", completed),
    );
  });
  const events = [];
  const result = await streamChat(
    "测试问题",
    "existing-session",
    "fixture-token",
    (event) => events.push(event),
    new AbortController().signal,
  );
  assert.deepEqual(result, completed);
  assert.equal(
    events
      .filter((event) => event.event === "delta")
      .map((event) => event.data.text)
      .join(""),
    completed.answer,
  );
});

test("premature EOF and stream errors never become saved successes", async (t) => {
  t.mock.method(globalThis, "fetch", async () =>
    mockResponse(frame("delta", { text: "部分答案" })),
  );
  await assert.rejects(
    streamChat(
      "问题",
      undefined,
      "test",
      () => {},
      new AbortController().signal,
    ),
    /连接已中断/,
  );
  globalThis.fetch = async () =>
    mockResponse(frame("error", { detail: "测试服务不可用" }));
  await assert.rejects(
    streamChat(
      "问题",
      undefined,
      "test",
      () => {},
      new AbortController().signal,
    ),
    /测试服务不可用/,
  );
});

test("HTTP errors and malformed done events are surfaced", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async () =>
      new Response(JSON.stringify({ detail: "需要登录" }), { status: 401 }),
  );
  await assert.rejects(
    streamChat(
      "问题",
      undefined,
      "test",
      () => {},
      new AbortController().signal,
    ),
    /需要登录/,
  );
  globalThis.fetch = async () =>
    mockResponse(frame("done", { answer: "没有消息ID" }));
  await assert.rejects(
    streamChat(
      "问题",
      undefined,
      "test",
      () => {},
      new AbortController().signal,
    ),
    /响应格式不正确/,
  );
  assert.equal(parseFrame(": heartbeat"), null);
});
