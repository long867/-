"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { LayoutList, ListTree, Loader2 } from "lucide-react";
import { ArticleCard } from "./article-card";
import { FeedFiltersBar } from "./feed-filters";
import { EmptyState, ErrorState, SkeletonCards } from "./ui/states";
import { publicApi } from "@/lib/api";
import {
  useUrlFilters,
  filterParams,
  type FeedFilters,
} from "@/hooks/use-url-filters";
import { usePreferences } from "@/hooks/use-preferences";
import type { Article, ArticlePage, Facets } from "@/types";
export function ArticleFeed({
  initial,
  initialFacets,
  mineral,
  region,
  hideFilters = false,
}: {
  initial?: ArticlePage;
  initialFacets?: Facets;
  mineral?: string;
  region?: string;
  hideFilters?: boolean;
}) {
  const { t } = usePreferences();
  const { filters, update, ready } = useUrlFilters();
  const [view, setView] = useState("cards");
  const sentinel = useRef<HTMLDivElement>(null);
  const [debounced, setDebounced] = useState(filters.search);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(filters.search), 250);
    return () => clearTimeout(timer);
  }, [filters.search]);
  useEffect(() => {
    setView(
      new URLSearchParams(location.search).get("view") === "timeline"
        ? "timeline"
        : "cards",
    );
  }, []);
  const effective: FeedFilters = {
    ...filters,
    search: debounced,
    minerals: mineral ? [mineral] : filters.minerals,
    regions: region ? [region] : filters.regions,
  };
  const pageSize = initial?.page_size ?? 4;
  const params = filterParams(effective);
  params.set("page_size", String(pageSize));
  const key = params.toString();
  const defaultQuery =
    !filters.minerals.length &&
    !filters.regions.length &&
    !filters.tags.length &&
    !filters.search &&
    !filters.category &&
    !filters.date_from &&
    !filters.date_to &&
    !filters.company &&
    filters.sort_by === "published_at";
  const query = useInfiniteQuery({
    queryKey: ["article-feed", mineral, region, key],
    queryFn: ({ pageParam }) => {
      const request = new URLSearchParams(params);
      request.set("page", String(pageParam));
      return publicApi<ArticlePage>(`/articles?${request}`);
    },
    initialPageParam: 1,
    getNextPageParam: (last) =>
      last.page * last.page_size < last.total ? last.page + 1 : undefined,
    initialData:
      initial && defaultQuery
        ? { pages: [initial], pageParams: [1] }
        : undefined,
    staleTime: initial && defaultQuery ? 300000 : 30000,
    enabled: ready,
  });
  const articles = useMemo(
    () =>
      Array.from(
        new Map(
          query.data?.pages
            .flatMap((page) => page.items)
            .map((article) => [article.id, article]) || [],
        ).values(),
      ),
    [query.data],
  );
  useEffect(() => {
    if (!sentinel.current || !query.hasNextPage) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (
          entries[0].isIntersecting &&
          !query.isFetchingNextPage &&
          !query.isError
        )
          query.fetchNextPage();
      },
      { rootMargin: "200px" },
    );
    observer.observe(sentinel.current);
    return () => observer.disconnect();
  }, [
    query.hasNextPage,
    query.isFetchingNextPage,
    query.isError,
    query.fetchNextPage,
  ]);
  function switchView(value: string) {
    setView(value);
    const params = new URLSearchParams(location.search);
    value === "timeline" ? params.set("view", value) : params.delete("view");
    history.replaceState(
      null,
      "",
      `${location.pathname}${params.size ? "?" + params : ""}`,
    );
  }
  const groups = new Map<string, Article[]>();
  for (const article of articles) {
    const date = article.published_at
      ? new Date(article.published_at).toLocaleDateString("en-CA", {
          timeZone: "Asia/Shanghai",
        })
      : t("日期未知", "Undated");
    groups.set(date, [...(groups.get(date) || []), article]);
  }
  const card = (article: Article) => (
    <ArticleCard
      article={article}
      key={article.id}
      query={filters.search}
      onTag={(tag) => update({ tags: [tag] })}
    />
  );
  return (
    <section aria-label={t("文章资讯流", "Article feed")}>
      <div className="feed-toolbar">
        <div className="feed-tabs">
          <button
            className={view === "cards" ? "selected" : ""}
            onClick={() => switchView("cards")}
            aria-pressed={view === "cards"}
          >
            <LayoutList size={13} />
            {t("资讯流", "Latest intelligence")}
          </button>
          <button
            className={view === "timeline" ? "selected" : ""}
            onClick={() => switchView("timeline")}
            aria-pressed={view === "timeline"}
          >
            <ListTree size={13} />
            {t("时间线", "Timeline")}
          </button>
        </div>
        <span className="stream-count">
          {query.data?.pages[0].total ?? "—"}{" "}
          {t("条可追溯资讯", "sourced articles")}
        </span>
      </div>
      {!hideFilters && (
        <FeedFiltersBar
          filters={filters}
          update={update}
          initialFacets={initialFacets}
        />
      )}
      {query.isPending ? (
        <SkeletonCards />
      ) : query.isError && !articles.length ? (
        <ErrorState error={query.error} retry={() => query.refetch()} />
      ) : !articles.length ? (
        <EmptyState />
      ) : view === "cards" ? (
        articles.map(card)
      ) : (
        Array.from(groups).map(([day, items]) => (
          <section className="timeline-day" key={day}>
            <div className="timeline-date">
              {day}
              <small>
                {items.length} {t("篇已加载报道", "loaded articles")}
              </small>
            </div>
            {items.map(card)}
          </section>
        ))
      )}
      <div className="load-more" ref={sentinel}>
        {query.isFetchingNextPage ? (
          <>
            <Loader2 size={14} className="animate-spin" />
            {t("加载更多资讯…", "Loading more…")}
          </>
        ) : query.hasNextPage ? (
          <button onClick={() => query.fetchNextPage()}>
            {t("继续加载", "Load more")} ↓
          </button>
        ) : articles.length > 0 ? (
          <span>
            {t(
              "已显示当前筛选下的全部资讯",
              "You've reached the end of this feed",
            )}
          </span>
        ) : null}
      </div>
      {query.isFetchNextPageError && (
        <ErrorState
          error={query.error as Error}
          retry={() => query.fetchNextPage()}
        />
      )}
    </section>
  );
}
