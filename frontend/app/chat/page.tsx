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
import { AGENT_NAME } from "@/lib/branding";

type Pending = {
  question: string;
  text: string;
  sources: Citation[];
  phase: string;
};
const phases: Record<string, string> = {
  retrieving: "正在检索证据…",
  answering: "正在分析原因、影响和应对建议…",
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
        <div className="eyebrow">MINING INTELLIGENCE AGENT</div>
        <h1>{AGENT_NAME}</h1>
        <p className="subtitle mb-6">
          {t(
            "矿产资源研究助手。结合资料分析原因、影响和应对措施，支持多轮追问与来源核对。",
            "Analyze mineral resources, implications and actions with follow-up questions and traceable facts.",
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
    <main className="small-page chat-workspace">
      <div className="eyebrow">EVIDENCE-BASED CONSULTATION</div>
      <div className="chat-heading flex justify-between items-center gap-3">
        <h1>{AGENT_NAME}</h1>
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
          "把问题讲给矿眸智探：分析为什么、会有什么影响，以及下一步怎么做。关键事实附来源，可继续追问。",
          "Discuss causes, implications and next steps. Key facts cite sources; keep asking follow-up questions.",
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
              "说说你关心什么，我们一起分析",
              "Tell me what matters. Let's analyze it together",
            )}
          </h2>
          <p className="subtitle">
            {t(
              "价格为什么变动？政策有什么影响？采购或项目该怎么应对？",
              "Why do prices move? What does policy change? What should procurement or projects do?",
            )}
          </p>
          <div className="quick-prompts">
            {[
              t(
                "最新碳酸锂现货报价是多少？",
                "What is the latest lithium carbonate spot quote?",
              ),
              t(
                "我负责采购，碳酸锂价格变化可能带来什么影响，应该怎么应对？",
                "How might lithium carbonate price changes affect procurement, and how should I respond?",
              ),
              t(
                "最近铜矿项目进展对供应有什么影响？帮我分析机会和风险。",
                "Analyze how recent copper projects might affect supply, opportunities and risks.",
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
            {item.result.mode === "analytical"
              ? t(
                  "AI分析 · 事实附来源，推断与建议请结合条件判断",
                  "AI analysis · cited facts, conditional inference and recommendations",
                )
              : item.result.mode === "general"
                ? t(
                    "行业知识与分析框架 · 不代表实时行情或已核实事件",
                    "Industry knowledge and analysis · not real-time market observations",
                  )
                : item.result.mode === "extractive"
                  ? t(
                      "中文资料摘录 · 可展开来源核对原文",
                      "Chinese evidence excerpts · inspect the original sources",
                    )
                  : item.result.mode === "grounded"
                    ? t(
                        "引用片段已校验 · 结论请结合原文判断",
                        "Verified citations · review the original context",
                      )
                    : item.result.mode === "identity"
                      ? t(
                          "矿眸智探 · 智能体介绍",
                          "矿眸智探 · About the assistant",
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
                    answering: "Analyzing causes, implications and actions…",
                    saving: "Saving conversation…",
                  } as Record<string, string>
                )[pending.phase] || "Processing…",
              )}
            </p>
          )}
        </article>
      )}
      <form
        className="form-card chat-composer mt-6"
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
