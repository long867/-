"use client";

import { usePreferences } from "@/hooks/use-preferences";
import { ArrowUpRight } from "lucide-react";
import type { Citation } from "@/types";

export function ChatAnswerBody({
  answer,
  sources,
  messageId,
}: {
  answer: string;
  sources: Citation[];
  messageId: string;
}) {
  const { t, language } = usePreferences();
  const cardId = (index: number) => `evidence-${messageId}-${index}`;
  function reveal(index: number) {
    const element = document.getElementById(cardId(index));
    if (element instanceof HTMLDetailsElement) {
      element.open = true;
      element.scrollIntoView({ behavior: "smooth", block: "center" });
      element.focus({ preventScroll: true });
    }
  }
  return (
    <>
      <div className="answer whitespace-pre-wrap" aria-live="polite">
        {answer.split(/(\[\d+\])/g).map((part, index) => {
          const match = /^\[(\d+)\]$/.exec(part);
          const number = match ? Number(match[1]) : undefined;
          return number && sources.some((source) => source.index === number) ? (
            <button
              type="button"
              key={index}
              className="text-accent underline mx-1"
              aria-label={` ${t("查看来源", "View source")} ${number}`}
              onClick={() => reveal(number)}
            >
              {part}
            </button>
          ) : (
            <span key={index}>{part}</span>
          );
        })}
      </div>
      {sources.map((source) => (
        <details
          className="evidence"
          tabIndex={-1}
          id={cardId(source.index)}
          key={`${source.index}-${source.chunk_id}`}
        >
          <summary className="cursor-pointer">
            [{source.index}] {source.title}
          </summary>
          <p className="text-xs text-muted my-2">
            {source.source_name || t("未知来源", "Unknown source")} ·{" "}
            {source.published_at
              ? new Date(source.published_at).toLocaleDateString(
                  language === "zh" ? "zh-CN" : "en-GB",
                  { timeZone: "Asia/Shanghai" },
                )
              : t("日期未提供", "Date not available")}
          </p>
          <blockquote>{source.snippet || source.quote}</blockquote>
          {/^https?:\/\//i.test(source.url) && (
            <a
              className="source-link mt-3"
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {t("查看原文", "Read original")} <ArrowUpRight size={12} />
            </a>
          )}
        </details>
      ))}
    </>
  );
}
