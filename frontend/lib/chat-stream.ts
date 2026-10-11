/** Parse UTF-8 SSE over authenticated POST, including fragmented network frames. */
import type { ChatAnswer, Citation } from "@/types";

export type ChatEvent =
  | { event: "status"; data: { phase: string } }
  | { event: "delta"; data: { text: string } }
  | { event: "sources"; data: { sources: Citation[] } }
  | { event: "done"; data: ChatAnswer };

export function parseFrame(
  frame: string,
): { event: string; data: unknown } | null {
  const lines = frame.split(/\r?\n/);
  const event = lines
    .find((line) => line.startsWith("event:"))
    ?.slice(6)
    .trim();
  const data = lines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).replace(/^ /, ""))
    .join("\n");
  if (!event || !data) return null;
  return { event, data: JSON.parse(data) };
}

export async function streamChat(
  question: string,
  sessionId: string | undefined,
  token: string,
  onEvent: (event: ChatEvent) => void,
  signal: AbortSignal,
): Promise<ChatAnswer> {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    signal,
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ question, session_id: sessionId }),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "咨询服务暂时不可用" }));
    throw new Error(
      typeof error.detail === "string" ? error.detail : "输入格式不正确",
    );
  }
  if (
    !response.body ||
    !response.headers.get("content-type")?.includes("text/event-stream")
  ) {
    throw new Error("咨询服务未返回有效的流式响应");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let result: ChatAnswer | undefined;
  function consume(frame: string) {
    const message = parseFrame(frame);
    if (!message) return;
    const data = message.data as Record<string, unknown>;
    if (message.event === "error")
      throw new Error(String(data.detail || "咨询失败"));
    if (message.event === "done") {
      if (
        typeof data.answer !== "string" ||
        typeof data.session_id !== "string" ||
        typeof data.message_id !== "string" ||
        !Array.isArray(data.sources)
      ) {
        throw new Error("咨询响应格式不正确");
      }
      result = data as unknown as ChatAnswer;
    }
    if (["status", "delta", "sources", "done"].includes(message.event)) {
      onEvent(message as ChatEvent);
    }
  }
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let match: RegExpExecArray | null;
      while ((match = /\r?\n\r?\n/.exec(buffer))) {
        consume(buffer.slice(0, match.index));
        buffer = buffer.slice(match.index + match[0].length);
      }
      if (buffer.length > 1_000_000) throw new Error("咨询响应过大");
      if (done) break;
    }
    if (buffer.trim()) consume(buffer);
    if (!result) throw new Error("连接已中断，请重试或检查会话历史");
    return result;
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
