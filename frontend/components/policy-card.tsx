"use client";
import { ArrowUpRight, Scale, Calendar } from "lucide-react";
import { usePreferences } from "@/hooks/use-preferences";
import { Highlight } from "./article-card";
import type { Policy } from "@/types";
export function PolicyCard({
  policy,
  query,
}: {
  policy: Policy;
  query?: string;
}) {
  const { t, language } = usePreferences();
  return (
    <article className="policy-card">
      <div className="flex justify-between gap-3 items-center">
        <span className="category-tag">{policy.country}</span>
        <span className="impact-score">
          <Scale size={12} />
          {t("影响评分", "Impact")}{" "}
          {policy.impact_score === 0
            ? t("待评估", "Unrated")
            : policy.impact_score.toFixed(0)}
        </span>
      </div>
      <h3 className="text-base leading-8 my-3">
        <a href={policy.url} target="_blank" rel="noopener noreferrer">
          <Highlight
            text={
              language === "zh" ? policy.title_zh || policy.title : policy.title
            }
            query={query}
          />
        </a>
      </h3>
      <div className="policy-meta">
        <span className="inline-flex items-center gap-1">
          <Calendar size={11} />
          {t("生效日期", "Effective date")} ·{" "}
          {policy.effective_date || t("未披露", "Not specified")}
        </span>
        <span>{policy.minerals.join(" · ")}</span>
      </div>
      {policy.summary_zh && (
        <p>
          <Highlight text={policy.summary_zh} query={query} />
        </p>
      )}
      <a
        className="source-link"
        href={policy.url}
        target="_blank"
        rel="noopener noreferrer"
      >
        {t("查看政策原文", "Read the original policy")}
        <ArrowUpRight size={12} />
      </a>
    </article>
  );
}
