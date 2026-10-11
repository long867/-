"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight } from "lucide-react";
import { publicApi } from "@/lib/api";
import { usePreferences } from "@/hooks/use-preferences";
import { useUrlFilters } from "@/hooks/use-url-filters";
import { SectionHeading } from "./section-heading";
import { ArticleCard } from "./article-card";
import { EmptyState, ErrorState, SkeletonCards } from "./ui/states";
import type { Article, EventPage, MineralEvent } from "@/types";
export function EventWorkspace({ id }: { id?: string }) {
  const { t } = usePreferences();
  const { filters, update, ready } = useUrlFilters();
  const [page, setPage] = useState(1);
  const params = new URLSearchParams({ page: String(page), page_size: "12" });
  if (filters.search) params.set("search", filters.search);
  if (filters.minerals[0]) params.set("mineral", filters.minerals[0]);
  if (filters.regions[0]) params.set("region", filters.regions[0]);
  const query = useQuery({
    queryKey: ["events", params.toString()],
    queryFn: () => publicApi<EventPage>(`/events?${params}`),
    enabled: ready && !id,
  });
  const detail = useQuery({
    queryKey: ["event", id],
    queryFn: () =>
      publicApi<MineralEvent & { articles: Article[] }>(`/events/${id}`),
    enabled: !!id,
  });
  const active = id ? detail : query;
  return (
    <main className="workspace">
      <SectionHeading
        eyebrow="CONNECTED COVERAGE"
        zh={id ? detail.data?.title_zh || "事件详情" : "全球事件时间线"}
        en={
          id ? detail.data?.title_zh || "Event detail" : "Global event timeline"
        }
        description="聚合同一事件的不同信源报道，保留原始依据。"
        descriptionEn="Follow an event across sources, with its original evidence."
      />
      {!id && (
        <div className="filter-panel">
          <input
            aria-label={t("搜索事件", "Search events")}
            placeholder={t("搜索事件关键词…", "Search event keywords…")}
            value={filters.search}
            onChange={(e) => {
              setPage(1);
              update({ search: e.target.value });
            }}
          />
        </div>
      )}
      {active.isError ? (
        <ErrorState
          error={active.error as Error}
          retry={() => active.refetch()}
        />
      ) : active.isPending ? (
        <SkeletonCards />
      ) : id ? (
        <>
          <div className="panel mb-6">
            <p className="leading-8">{detail.data?.summary_zh}</p>
            <div className="article-meta mt-5">
              {detail.data?.article_count} {t("篇报道", "articles")} ·{" "}
              {detail.data?.minerals.join(" · ")} ·{" "}
              {detail.data?.regions.join(" · ")}
            </div>
          </div>
          {detail.data?.articles.map((a) => (
            <ArticleCard article={a} key={a.id} />
          ))}
        </>
      ) : query.data?.items.length ? (
        <>
          <div className="timeline-list">
            {query.data.items.map((e) => (
              <div className="timeline-group" key={e.id}>
                <div className="timeline-date">
                  {new Date(e.last_updated_at).toLocaleDateString("en-CA", {
                    timeZone: "Asia/Shanghai",
                  })}
                </div>
                <article className="article-card">
                  <div className="article-meta">
                    <span>
                      {e.article_count} {t("篇报道", "articles")}
                    </span>
                    <span>{e.minerals.join(" · ")}</span>
                    <span className="ml-auto">
                      {t("重要性", "Importance")}{" "}
                      {Math.round(e.importance_score)}
                    </span>
                  </div>
                  <h3>
                    <Link href={`/events/${e.id}`}>{e.title_zh}</Link>
                  </h3>
                  <p className="article-summary">{e.summary_zh}</p>
                  <Link className="source-link" href={`/events/${e.id}`}>
                    {t("查看完整报道", "Explore coverage")}
                    <ArrowUpRight size={12} />
                  </Link>
                </article>
              </div>
            ))}
          </div>
          <div className="pagination">
            <button
              className="btn btn-outline"
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
            >
              {t("上一页", "Previous")}
            </button>
            <span>{page}</span>
            <button
              className="btn btn-outline"
              disabled={page * 12 >= query.data.total}
              onClick={() => setPage((p) => p + 1)}
            >
              {t("下一页", "Next")}
            </button>
          </div>
        </>
      ) : (
        <EmptyState />
      )}
    </main>
  );
}
