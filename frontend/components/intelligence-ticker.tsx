"use client";
import Link from "next/link";
import { Radio } from "lucide-react";
import { usePreferences } from "@/hooks/use-preferences";
import type { Article } from "@/types";

/** Repeat real headlines for a seamless ticker; duplicate links leave the tab order. */
export function IntelligenceTicker({ articles }: { articles: Article[] }) {
  const { t, language } = usePreferences();
  if (!articles.length) return null;
  return (
    <section
      className="intelligence-ticker"
      aria-label={t("情报快讯", "Intelligence briefing")}
    >
      <div className="ticker-label">
        <Radio size={12} />
        <span>{t("情报快讯", "IN BRIEF")}</span>
      </div>
      <div className="ticker-window">
        <div className="ticker-track">
          {[0, 1].map((copy) => (
            <div
              className="ticker-group"
              key={copy}
              aria-hidden={copy === 1 ? true : undefined}
            >
              {articles.map((article) => (
                <Link
                  href={`/articles/${article.id}`}
                  prefetch={false}
                  key={article.id}
                  tabIndex={copy === 1 ? -1 : undefined}
                >
                  <span className="ticker-category">
                    {article.minerals[0] || t("矿产", "MINERALS")}
                  </span>
                  <span>
                    {language === "zh"
                      ? article.title_zh || article.title
                      : article.title}
                  </span>
                  <span className="ticker-source">{article.source_name}</span>
                  <span className="ticker-separator" aria-hidden="true">
                    ✦
                  </span>
                </Link>
              ))}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
