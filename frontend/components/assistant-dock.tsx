"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowUpRight, Gem, Send, X } from "lucide-react";
import { usePreferences } from "@/hooks/use-preferences";
import { AGENT_NAME } from "@/lib/branding";

/** Keep consultation within reach without covering the mobile reading column. */
export function AssistantDock() {
  const path = usePathname();
  const { t } = usePreferences();
  const [open, setOpen] = useState(false);
  const [overHero, setOverHero] = useState(path === "/");
  const shell = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    setOpen(false);
  }, [path]);
  useEffect(() => {
    const hero = document.querySelector(".observatory-hero");
    if (!hero) {
      setOverHero(false);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => setOverHero(entry.isIntersecting),
      { rootMargin: "-80px 0px 0px" },
    );
    observer.observe(hero);
    return () => observer.disconnect();
  }, [path]);
  useEffect(() => {
    if (!open) return;
    input.current?.focus({ preventScroll: true });
    const close = (event: PointerEvent) => {
      if (
        event.target instanceof Node &&
        !shell.current?.contains(event.target)
      )
        setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open]);
  if (path.startsWith("/chat") || path.startsWith("/admin")) return null;
  return (
    <div
      className="assistant-dock"
      data-over-hero={overHero && !open ? "true" : undefined}
      ref={shell}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          setOpen(false);
          trigger.current?.focus();
        }
      }}
    >
      {open && (
        <section
          className="assistant-dock-panel"
          id="assistant-quick-panel"
          role="dialog"
          aria-label={t("向矿眸智探提问", "Ask 矿眸智探")}
        >
          <div className="assistant-dock-heading">
            <span>
              <Gem size={17} /> {AGENT_NAME}
            </span>
            <button
              type="button"
              aria-label={t("关闭提问面板", "Close consultation panel")}
              onClick={() => {
                setOpen(false);
                trigger.current?.focus();
              }}
            >
              <X size={16} />
            </button>
          </div>
          <p>
            {t(
              "从一条线索，找到有依据的答案。",
              "Follow a signal. Find an answer backed by evidence.",
            )}
          </p>
          <div className="assistant-quick-questions">
            {[
              t(
                "最近有哪些铜矿项目进展？",
                "What are the latest copper project developments?",
              ),
              t(
                "最新碳酸锂现货报价是多少？",
                "What is the latest lithium carbonate spot quote?",
              ),
            ].map((question) => (
              <Link
                href={`/chat?q=${encodeURIComponent(question)}`}
                key={question}
                prefetch={false}
              >
                {question}
                <ArrowUpRight size={13} />
              </Link>
            ))}
          </div>
          <form action="/chat" className="assistant-dock-form">
            <input
              ref={input}
              name="q"
              required
              minLength={2}
              maxLength={2000}
              placeholder={t(
                "输入矿产相关问题…",
                "Ask about mineral resources…",
              )}
              aria-label={t("咨询问题", "Consultation question")}
            />
            <button
              aria-label={t("提交咨询问题", "Submit consultation question")}
            >
              <Send size={15} />
            </button>
          </form>
          <small>
            {t(
              "回答附原文来源 · 登录后保存会话",
              "Original citations · Sign in to save conversations",
            )}
          </small>
        </section>
      )}
      <button
        ref={trigger}
        className="assistant-dock-trigger"
        type="button"
        aria-label={t("打开矿眸智探", "Open 矿眸智探")}
        aria-expanded={open}
        aria-controls="assistant-quick-panel"
        onClick={() => setOpen(!open)}
      >
        <span className="assistant-gem">
          <Gem size={20} />
        </span>
        <span>
          {AGENT_NAME}
          <small>{t("让情报成为洞察", "FROM EVIDENCE TO INSIGHT")}</small>
        </span>
        <ArrowUpRight size={15} />
      </button>
    </div>
  );
}
