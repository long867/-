"use client";
import Link from "next/link";
import { usePreferences } from "@/hooks/use-preferences";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Send, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { streamChat } from "@/lib/chat-stream";
import { useAuth } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { ChatAnswerBody } from "@/components/chat-answer";
import type { ChatAnswer, ChatMessage, Citation, Session } from "@/types";

type Pending = {
  question: string;
  text: string;
  sources: Citation[];
  phase: string;
};
const phases: Record<string, string> = {
  retrieving: "正在检索证据…",
  answering: "正在整理答案并校验引用…",
  saving: "正在保存会话…",
};

export default function Chat() {
  const auth = useAuth();
  const { t } = usePreferences();
  const client = useQueryClient();
  const [question, setQuestion] = useState("");
  const [sessionId, setSessionId] = useState<string>();
  const [answers, setAnswers] = useState<
    { question: string; result: ChatAnswer }[]
  >([]);
  const [pending, setPending] = useState<Pending>();
  const controller = useRef<AbortController>();
  useEffect(() => {
    const suggested = new URLSearchParams(location.search).get("q");
    if (suggested) setQuestion(suggested.slice(0, 2000));
  }, []);
  useEffect(() => {
    setAnswers([]);
    setSessionId(undefined);
    setPending(undefined);
    return () => controller.current?.abort();
  }, [auth.user?.id]);
  const sessions = useQuery({
    queryKey: ["sessions", auth.user?.id],
    queryFn: () => api<Session[]>("/chat/sessions", {}, auth.token),
    enabled: !!auth.token,
  });
  const history = useQuery({
    queryKey: ["chat-history", auth.user?.id, sessionId],
    queryFn: () =>
      api<ChatMessage[]>(`/chat/history/${sessionId}`, {}, auth.token),
    enabled: !!auth.token && !!sessionId,
  });
  const mutation = useMutation({
    mutationFn: async (text: string) => {
      if (!auth.token) throw new Error("请先登录");
      controller.current = new AbortController();
      setPending({
        question: text,
        text: "",
        sources: [],
        phase: "retrieving",
      });
      return streamChat(
        text,
        sessionId,
        auth.token,
        (message) => {
          setPending((previous) => {
            if (!previous) return previous;
            if (message.event === "status")
              return { ...previous, phase: message.data.phase };
            if (message.event === "delta")
              return { ...previous, text: previous.text + message.data.text };
            if (message.event === "sources")
              return { ...previous, sources: message.data.sources };
            return previous;
          });
        },
        controller.current.signal,
      );
    },
    onSuccess: (result, text) => {
      setSessionId(result.session_id);
      setQuestion("");
      setPending(undefined);
      setAnswers((previous) => [...previous, { question: text, result }]);
      client.invalidateQueries({ queryKey: ["sessions", auth.user?.id] });
      client.invalidateQueries({
        queryKey: ["chat-history", auth.user?.id, result.session_id],
      });
    },
    onError: () => {
      setPending(undefined);
      client.invalidateQueries({ queryKey: ["sessions", auth.user?.id] });
      client.invalidateQueries({
        queryKey: ["chat-history", auth.user?.id, sessionId],
      });
    },
  });
  const deletion = useMutation({
    mutationFn: () =>
      api<void>(`/chat/session/${sessionId}`, { method: "DELETE" }, auth.token),
    onSuccess: () => {
      client.removeQueries({
        queryKey: ["chat-history", auth.user?.id, sessionId],
      });
      setSessionId(undefined);
      setAnswers([]);
      mutation.reset();
      client.invalidateQueries({ queryKey: ["sessions", auth.user?.id] });
    },
  });
  if (!auth.user)
    return (
      <main className="small-page">
        <h1>{t("基于证据的 AI 咨询", "Evidence-based AI consultation")}</h1>
        <p className="subtitle mb-6">
          {t(
            "登录后开始咨询，保留多轮会话和原文引用。",
            "Sign in to consult, save conversations and examine original evidence.",
          )}
        </p>
        <Button asChild>
          <Link
            href={`/login?next=${encodeURIComponent(`/chat${question ? `?q=${encodeURIComponent(question)}` : ""}`)}`}
          >
            {t("登录 / 注册", "Sign in / Register")}
          </Link>
        </Button>
      </main>
    );
  const stored = (history.data || []).map((item) => ({
    question: item.question,
    result: {
      session_id: item.session_id,
      message_id: item.id,
      answer: item.answer,
      sources: item.sources_json,
      mode: item.mode,
    } as ChatAnswer,
  }));
  const merged = [
    ...stored,
    ...answers.filter(
      (item) =>
        item.result.session_id === sessionId &&
        !stored.some((row) => row.result.message_id === item.result.message_id),
    ),
  ];
  const busy = mutation.isPending || deletion.isPending;
  return (
    <main className="small-page">
      <div className="eyebrow">EVIDENCE-BASED CONSULTATION</div>
      <div className="flex justify-between items-center gap-3">
        <h1>{t("把问题交给情报。", "Let evidence answer.")}</h1>
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => {
            setSessionId(undefined);
            setAnswers([]);
            mutation.reset();
            deletion.reset();
          }}
        >
          <Plus size={14} />
          {t("新会话", "New conversation")}
        </Button>
      </div>
      <p className="subtitle mb-6">
        {t(
          "点击答案中的来源编号可查看证据，支持继续追问。",
          "Click a source number to inspect evidence, then ask follow-up questions.",
        )}
      </p>
      <div className="flex gap-3 mb-4">
        <select
          className="w-full"
          aria-label={t("选择历史会话", "Select conversation")}
          disabled={busy}
          value={sessionId || ""}
          onChange={(event) => {
            setSessionId(event.target.value || undefined);
            setAnswers([]);
            mutation.reset();
            deletion.reset();
          }}
        >
          <option value="">{t("新会话", "New conversation")}</option>
          {sessions.data?.map((item) => (
            <option key={item.id} value={item.id}>
              {item.title}
            </option>
          ))}
        </select>
        {sessionId && (
          <Button
            variant="outline"
            disabled={busy}
            aria-label={t("删除当前会话", "Delete conversation")}
            onClick={() => {
              if (
                window.confirm(
                  t(
                    "删除此会话和全部问答记录？",
                    "Delete this conversation and all messages?",
                  ),
                )
              )
                deletion.mutate();
            }}
          >
            <Trash2 size={14} />
          </Button>
        )}
      </div>
      {(history.isError || sessions.isError || deletion.isError) && (
        <p role="alert" className="text-red-700">
          {history.error?.message ||
            sessions.error?.message ||
            deletion.error?.message}
        </p>
      )}
      {sessionId && history.isPending && (
        <p className="subtitle">
          {t("正在加载历史会话…", "Loading conversation…")}
        </p>
      )}
      {!merged.length && !pending && (
        <div className="chat-intro">
          <h2>
            {t(
              "从一个有依据的问题开始",
              "Start with a question grounded in evidence",
            )}
          </h2>
          <p className="subtitle">
            {t(
              "价格、政策、项目动态，都可以继续追问。",
              "Explore prices, policy and projects, with follow-up questions.",
            )}
          </p>
          <div className="quick-prompts">
            {[
              t(
                "最新碳酸锂现货报价是多少？",
                "What is the latest lithium carbonate spot quote?",
              ),
              t(
                "2026年锂矿价格走势如何？请列出来源。",
                "How are lithium prices trending in 2026? Cite sources.",
              ),
              t(
                "最近有哪些金矿项目进展？",
                "What are the latest gold project developments?",
              ),
            ].map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => setQuestion(q)}
                disabled={busy}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}
      {merged.map((item) => (
        <article className="message" key={item.result.message_id}>
          <div className="question">{item.question}</div>
          <ChatAnswerBody
            answer={item.result.answer}
            sources={item.result.sources}
            messageId={item.result.message_id}
          />
          <p className="text-xs text-muted mt-3">
            {item.result.mode === "extractive"
              ? t(
                  "原文证据摘录 · 生成服务未启用或暂时不可用",
                  "Evidence excerpts · generation unavailable",
                )
              : item.result.mode === "grounded"
                ? t(
                    "引用片段已校验 · 结论请结合原文判断",
                    "Verified citations · review the original context",
                  )
                : t("证据不足", "Insufficient evidence")}
          </p>
        </article>
      ))}
      {pending && (
        <article className="message" aria-busy="true">
          <div className="question">{pending.question}</div>
          {pending.text ? (
            <ChatAnswerBody
              answer={pending.text}
              sources={pending.sources}
              messageId="streaming"
            />
          ) : (
            <p role="status">
              {t(
                phases[pending.phase] || "正在处理…",
                (
                  {
                    retrieving: "Retrieving evidence…",
                    answering: "Drafting and verifying citations…",
                    saving: "Saving conversation…",
                  } as Record<string, string>
                )[pending.phase] || "Processing…",
              )}
            </p>
          )}
        </article>
      )}
      <form
        className="form-card mt-6"
        onSubmit={(event) => {
          event.preventDefault();
          if (!busy && question.trim().length >= 2)
            mutation.mutate(question.trim());
        }}
      >
        <label htmlFor="question">
          {t("你的矿产资源问题", "Your mineral resources question")}
        </label>
        <textarea
          id="question"
          rows={4}
          minLength={2}
          maxLength={2000}
          placeholder={t(
            "例如：2026年锂矿价格走势如何？请列出来源。",
            "For example: How are lithium prices trending in 2026? Cite sources.",
          )}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          required
        />
        {mutation.isError && (
          <p role="alert" className="text-red-700 mt-4">
            {mutation.error.name === "AbortError"
              ? t(
                  "已停止接收，请检查会话历史后继续提问。",
                  "Stopped receiving. Check conversation history before continuing.",
                )
              : mutation.error.message}
          </p>
        )}
        <div className="flex gap-3 mt-4">
          <Button disabled={busy || question.trim().length < 2}>
            {mutation.isPending
              ? t("正在咨询…", "Consulting…")
              : t("发送问题", "Send question")}
            <Send size={14} />
          </Button>
          {mutation.isPending && (
            <Button
              type="button"
              variant="outline"
              onClick={() => controller.current?.abort()}
            >
              {t("停止接收", "Stop receiving")}
            </Button>
          )}
        </div>
      </form>
    </main>
  );
}
