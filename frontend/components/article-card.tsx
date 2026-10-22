"use client";
import Link from "next/link";
import { useId, useState, type ReactNode } from "react";
import {
  Bookmark,
  Share2,
  ArrowUpRight,
  ShieldCheck,
  ChevronDown,
} from "lucide-react";
import { usePreferences } from "@/hooks/use-preferences";
import { formatDate } from "@/lib/format-date";
import type { Article, Source } from "@/types";
export const categoryLabels: Record<string, [string, string]> = {
  news: ["市场资讯", "Market news"],
  price: ["价格行情", "Prices"],
  policy: ["政策动态", "Policy"],
  report: ["研究报告", "Research"],
  company: ["公司公告", "Company"],
};
export function Highlight({ text, query }: { text: string; query?: string }) {
  if (!query?.trim()) return <>{text}</>;
  const needle = query.trim().toLocaleLowerCase();
  const lower = text.toLocaleLowerCase();
  const parts: ReactNode[] = [];
  let cursor = 0,
    index = lower.indexOf(needle);
  while (index >= 0) {
    parts.push(
      text.slice(cursor, index),
      <mark key={index}>{text.slice(index, index + needle.length)}</mark>,
    );
    cursor = index + needle.length;
    index = lower.indexOf(needle, cursor);
  }
  parts.push(text.slice(cursor));
  return <>{parts}</>;
}
export function ArticleCard({
  article,
  source,
  onTag,
  query,
  expandedSummary = false,
}: {
  article: Article;
  source?: Source;
  onTag?: (name: string) => void;
  query?: string;
  expandedSummary?: boolean;
}) {
  const { t, language, saved, toggleSaved } = usePreferences();
  const [notice, setNotice] = useState("");
  const [expanded, setExpanded] = useState(expandedSummary);
  const summaryId = useId();
  const title =
    language === "zh" ? article.title_zh || article.title : article.title;
  const summary =
    language === "zh"
      ? article.summary_zh || article.summary
      : article.summary || article.summary_zh;
  const category = categoryLabels[article.category] || [
    article.category,
    article.category,
  ];
  async function share() {
    try {
      const url = `${location.origin}/articles/${article.id}`;
      if (navigator.share) await navigator.share({ title, url });
      else {
        await navigator.clipboard.writeText(url);
        setNotice(t("链接已复制", "Link copied"));
      }
    } catch (error) {
      if (error instanceof Error && error.name !== "AbortError")
        setNotice(
          t(
            "无法复制，请使用原文链接",
            "Unable to copy; use the original link",
          ),
        );
    }
  }
  return (
    <article
      className="article-card"
      data-article-id={article.id}
      data-mineral={article.minerals[0]}
    >
      <div className="article-meta">
        <span className="category-tag">{t(...category)}</span>
        <span>
          {article.source_name ||
            source?.name ||
            t("原始信源", "Original source")}
        </span>
        <span>·</span>
        <time dateTime={article.published_at || undefined}>
          {article.date_precision === "day" && article.published_at
            ? new Date(article.published_at).toLocaleDateString(
                language === "zh" ? "zh-CN" : "en-GB",
                { timeZone: "Asia/Shanghai" },
              )
            : formatDate(article.published_at)}
        </time>
        <span className="ml-auto">
          {article.language.toUpperCase()}
          {article.is_translated ? t(" · 已译", " · translated") : ""}
        </span>
      </div>
      <h3>
        <Link href={`/articles/${article.id}`} prefetch={false}>
          <Highlight text={title} query={query} />
        </Link>
      </h3>
      {summary && (
        <p
          id={summaryId}
          className={`article-summary ${expanded ? "is-expanded" : ""}`}
        >
          <Highlight text={summary} query={query} />
        </p>
      )}
      {summary && summary.length > 160 && !expandedSummary && (
        <button
          className="summary-control"
          aria-expanded={expanded}
          aria-controls={summaryId}
          onClick={() => setExpanded((value) => !value)}
        >
          {t(
            expanded ? "收起摘要" : "展开摘要",
            expanded ? "Less" : "Read summary",
          )}
          <ChevronDown size={13} />
        </button>
      )}
      <div className="article-bottom">
        <div className="article-tags">
          {article.minerals.map((name) => (
            <Link key={name} href={`/minerals/${encodeURIComponent(name)}`}>
              {name}
            </Link>
          ))}
          {article.regions.slice(0, 3).map((name) => (
            <Link key={name} href={`/regions/${encodeURIComponent(name)}`}>
              {name}
            </Link>
          ))}
          {article.tags.slice(0, 2).map((name) =>
            onTag ? (
              <button key={name} onClick={() => onTag(name)}>
                {name}
              </button>
            ) : (
              <Link href={`/?tags=${encodeURIComponent(name)}`} key={name}>
                {name}
              </Link>
            ),
          )}
        </div>
        <div className="article-actions">
          <span
            className="score"
            title={t(
              "来源质量分，非投资评级",
              "Source quality, not an investment rating",
            )}
          >
            <ShieldCheck size={11} />
            {Math.round(article.quality_score)}
          </span>
          <button
            className={`icon-button ${saved.includes(article.id) ? "active" : ""}`}
            onClick={() => toggleSaved(article.id)}
            aria-label={
              saved.includes(article.id)
                ? t("取消收藏", "Remove bookmark")
                : t("收藏文章", "Save article")
            }
            aria-pressed={saved.includes(article.id)}
          >
            <Bookmark
              size={13}
              fill={saved.includes(article.id) ? "currentColor" : "none"}
            />
          </button>
          <button
            className="icon-button"
            onClick={share}
            aria-label={t("分享文章", "Share article")}
          >
            <Share2 size={13} />
          </button>
          <a
            className="icon-button"
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={t("查看原文", "Read original")}
          >
            <ArrowUpRight size={14} />
          </a>
        </div>
      </div>
      {notice && (
        <p className="success-notice" role="status">
          {notice}
        </p>
      )}
    </article>
  );
}
