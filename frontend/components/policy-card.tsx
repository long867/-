"use client";
import { ArrowUpRight, Scale, Calendar } from "lucide-react";
import Link from "next/link";
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
        <span>
          {policy.publication_basis === "document_issue_date"
            ? t("原文件公布日", "Document issued")
            : t("资料发布日期", "Source published")}{" "}
          ·{" "}
          {policy.published_at
            ? new Date(policy.published_at).toLocaleDateString("zh-CN", {
                timeZone: "Asia/Shanghai",
              })
            : t("未披露", "Not specified")}
        </span>
        <span className="inline-flex items-center gap-1">
          <Calendar size={11} />
          {t("生效日期", "Effective date")} ·{" "}
          {policy.effective_date || t("未披露", "Not specified")}
        </span>
        <span>
          {policy.minerals.join(" · ") ||
            t("综合矿产资源", "General mineral resources")}
        </span>
      </div>
      <div className="flex flex-wrap gap-2 my-3">
        <span className="tag">
          {(
            {
              strategy: "战略规划",
              regulation: "法规文件",
              proposal: "立法进展",
              policy: "政策资料",
            } as Record<string, string>
          )[policy.document_kind || "policy"] || "政策资料"}
        </span>
        {policy.themes?.map((theme) => (
          <span className="tag" key={theme}>
            {theme}
          </span>
        ))}
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
      <Link
        className="source-link mt-3"
        href={`/research?region=${encodeURIComponent(policy.country)}`}
        prefetch={false}
      >
        {t("研判影响与应对", "Explore implications")} <ArrowUpRight size={12} />
      </Link>
    </article>
  );
}
