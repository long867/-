"use client";
import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowUpRight, FileText } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { publicApi } from "@/lib/api";
import { usePreferences } from "@/hooks/use-preferences";
import { ArticleCard } from "./article-card";
import { ErrorState, SkeletonCards } from "./ui/states";
import type { Article, ArticlePage } from "@/types";
export function ArticleDetail({
  id,
  initial,
}: {
  id: string;
  initial?: Article;
}) {
  const { t } = usePreferences();
  const [original, setOriginal] = useState(false);
  const query = useQuery({
    queryKey: ["article", id],
    queryFn: () => publicApi<Article>(`/articles/${id}`),
    initialData: initial,
    staleTime: 0,
  });
  const article = query.data;
  const related = useQuery({
    queryKey: ["article-related", id, article?.minerals[0]],
    queryFn: () =>
      publicApi<ArticlePage>(
        `/articles?mineral=${encodeURIComponent(article?.minerals[0] || "")}&page_size=4`,
      ),
    enabled: !!article?.minerals[0],
  });
  return (
    <main className="workspace">
      <Link href="/" className="source-link mb-6">
        <ArrowLeft size={14} />
        {t("返回情报流", "Back to intelligence")}
      </Link>
      {query.isError ? (
        <ErrorState error={query.error} retry={() => query.refetch()} />
      ) : query.isPending ? (
        <SkeletonCards count={2} />
      ) : (
        article && (
          <div className="article-detail-layout">
            <section>
              <ArticleCard article={article} />
              <div className="panel">
                <div className="flex flex-wrap gap-4 justify-between items-center mb-5">
                  <h2 className="inline-flex items-center gap-2">
                    <FileText size={18} />
                    {t("正文", "Article text")}
                  </h2>
                  <div className="tabs">
                    <button
                      className={!original ? "active" : ""}
                      onClick={() => setOriginal(false)}
                    >
                      {t("中文译文", "Chinese translation")}
                    </button>
                    <button
                      className={original ? "active" : ""}
                      onClick={() => setOriginal(true)}
                    >
                      {t("原文", "Original")}
                    </button>
                  </div>
                </div>
                <div className="reading-content">
                  {original
                    ? article.content
                    : article.content_zh ||
                      article.content ||
                      t(
                        "当前尚无完整正文，请查看原文。",
                        "Full text is unavailable. Read the original source.",
                      )}
                </div>
                <a
                  className="btn btn-outline mt-6"
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {t("前往原始信源", "Open original source")}
                  <ArrowUpRight size={14} />
                </a>
              </div>
            </section>
            <aside>
              <div className="panel">
                <div className="eyebrow">CONTEXT</div>
                <h2 className="my-4">
                  {t("文章关联", "Connected intelligence")}
                </h2>
                <dl className="detail-facts">
                  <dt>{t("矿种", "Minerals")}</dt>
                  <dd>
                    {article.minerals.map((n) => (
                      <Link href={`/minerals/${encodeURIComponent(n)}`} key={n}>
                        {n}
                      </Link>
                    ))}
                  </dd>
                  <dt>{t("地区", "Regions")}</dt>
                  <dd>
                    {article.regions.map((n) => (
                      <Link href={`/regions/${encodeURIComponent(n)}`} key={n}>
                        {n}
                      </Link>
                    ))}
                  </dd>
                  <dt>{t("公司", "Companies")}</dt>
                  <dd>
                    {article.companies.length
                      ? article.companies.map((n) => (
                          <Link
                            href={`/?company=${encodeURIComponent(n)}`}
                            key={n}
                          >
                            {n}
                          </Link>
                        ))
                      : t("未识别", "Not identified")}
                  </dd>
                  <dt>{t("项目", "Projects")}</dt>
                  <dd>
                    {article.projects.join(" · ") ||
                      t("未披露", "Not specified")}
                  </dd>
                </dl>
                {article.event_id && (
                  <Link
                    className="source-link mt-5"
                    href={`/events/${article.event_id}`}
                  >
                    {t("关联事件", "Related event")}
                    <ArrowUpRight size={12} />
                  </Link>
                )}
              </div>
              <div className="section-bar mt-7">
                <h2>{t("延伸阅读", "More coverage")}</h2>
              </div>
              {related.data?.items
                .filter((a) => a.id !== id)
                .slice(0, 3)
                .map((a) => (
                  <ArticleCard key={a.id} article={a} />
                ))}
            </aside>
          </div>
        )
      )}
    </main>
  );
}
