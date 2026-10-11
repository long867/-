"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, ArrowUpRight } from "lucide-react";
import { publicApi } from "@/lib/api";
import { useUrlFilters } from "@/hooks/use-url-filters";
import { usePreferences } from "@/hooks/use-preferences";
import { ArticleCard, Highlight, categoryLabels } from "./article-card";
import { PolicyCard } from "./policy-card";
import { SectionHeading } from "./section-heading";
import { EmptyState, ErrorState, SkeletonCards } from "./ui/states";
import type { Facets, SearchResults } from "@/types";
export function SearchWorkspace() {
  const { t } = usePreferences();
  const { filters, update, ready } = useUrlFilters();
  const [draft, setDraft] = useState("");
  const [page, setPage] = useState(1);
  const [tab, setTab] = useState<"articles" | "events" | "policies">(
    "articles",
  );
  useEffect(() => setDraft(filters.search), [filters.search]);
  const facets = useQuery({
    queryKey: ["facets"],
    queryFn: () => publicApi<Facets>("/facets"),
    staleTime: 300000,
  });
  const params = new URLSearchParams({
    q: filters.search,
    limit: "10",
    page: String(page),
  });
  if (filters.minerals[0]) params.set("mineral", filters.minerals[0]);
  if (filters.regions[0]) params.set("region", filters.regions[0]);
  for (const key of ["category", "date_from", "date_to"] as const)
    if (filters[key]) params.set(key, filters[key]);
  const results = useQuery({
    queryKey: ["global-search", params.toString()],
    queryFn: () => publicApi<SearchResults>(`/search?${params}`),
    enabled: ready && !!filters.search.trim(),
  });
  function change(values: Parameters<typeof update>[0]) {
    setPage(1);
    update(values);
  }
  const data = results.data;
  const count = data?.counts[tab] || 0;
  return (
    <main className="workspace">
      <SectionHeading
        eyebrow="SEARCH THE EVIDENCE"
        zh="找到信息，也找到依据。"
        en="Find the intelligence. Find the evidence."
        description="检索文章、事件与政策，按矿种、地区及日期缩小范围。"
        descriptionEn="Search coverage, events and policies with precise filters."
      />
      <form
        className="search-main"
        onSubmit={(e) => {
          e.preventDefault();
          change({ search: draft.trim() });
        }}
      >
        <Search size={22} className="text-accent" />
        <input
          aria-label={t("搜索关键词", "Search query")}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={200}
          required
          placeholder={t(
            "搜索矿种、公司、项目或政策…",
            "Search minerals, companies, projects or policy…",
          )}
        />
        <button className="btn">{t("搜索", "Search")}</button>
      </form>
      <div className="filter-panel mt-5">
        <div className="filter-toolbar">
          <select
            aria-label={t("搜索矿种", "Search mineral")}
            value={filters.minerals[0] || ""}
            onChange={(e) =>
              change({ minerals: e.target.value ? [e.target.value] : [] })
            }
          >
            <option value="">{t("全部矿种", "All minerals")}</option>
            {facets.data?.minerals.map((x) => (
              <option key={x.name}>{x.name}</option>
            ))}
          </select>
          <select
            aria-label={t("搜索地区", "Search region")}
            value={filters.regions[0] || ""}
            onChange={(e) =>
              change({ regions: e.target.value ? [e.target.value] : [] })
            }
          >
            <option value="">{t("全部地区", "All regions")}</option>
            {facets.data?.regions.map((x) => (
              <option key={x.name}>{x.name}</option>
            ))}
          </select>
          <select
            aria-label={t("文章类型", "Article type")}
            value={filters.category}
            onChange={(e) => change({ category: e.target.value })}
          >
            <option value="">{t("全部文章类型", "All article types")}</option>
            {Object.entries(categoryLabels).map(([k, v]) => (
              <option value={k} key={k}>
                {t(...v)}
              </option>
            ))}
          </select>
          <label className="date-filter">
            {t("日期起", "Date from")}
            <input
              type="date"
              value={filters.date_from}
              onChange={(e) => change({ date_from: e.target.value })}
            />
          </label>
          <label className="date-filter">
            {t("日期止", "Date to")}
            <input
              type="date"
              value={filters.date_to}
              onChange={(e) => change({ date_to: e.target.value })}
            />
          </label>
        </div>
        <p className="text-xs text-muted mt-3">
          {t(
            "文章与事件按报道时间筛选；政策按生效日期筛选。",
            "Dates apply to publication for coverage and events, and effective dates for policies.",
          )}
        </p>
      </div>
      {!filters.search ? (
        <EmptyState
          title={t("从一个关键词开始", "Start with a keyword")}
          detail={t(
            "尝试：锂、碳酸锂、公司名称或项目名称。",
            "Try lithium, a company name or a project name.",
          )}
        />
      ) : (
        <>
          <div
            className="tabs my-6"
            role="tablist"
            aria-label={t("搜索结果类型", "Search result type")}
          >
            {(
              [
                ["articles", "文章", "Articles"],
                ["events", "事件", "Events"],
                ["policies", "政策", "Policies"],
              ] as const
            ).map(([k, zh, en]) => (
              <button
                key={k}
                role="tab"
                aria-selected={tab === k}
                className={tab === k ? "active" : ""}
                onClick={() => {
                  setTab(k);
                  setPage(1);
                }}
              >
                {t(zh, en)}{" "}
                <span className="text-xs">{data?.counts[k] ?? "—"}</span>
              </button>
            ))}
          </div>
          {results.isError ? (
            <ErrorState error={results.error} retry={() => results.refetch()} />
          ) : results.isPending ? (
            <SkeletonCards />
          ) : count === 0 ? (
            <EmptyState title={t("没有找到相关结果", "No matching results")} />
          ) : tab === "articles" ? (
            data?.articles.map((a) => (
              <ArticleCard article={a} key={a.id} query={filters.search} />
            ))
          ) : tab === "policies" ? (
            <div className="policy-grid">
              {data?.policies.map((p) => (
                <PolicyCard policy={p} key={p.id} query={filters.search} />
              ))}
            </div>
          ) : (
            data?.events.map((e) => (
              <article className="article-card" key={e.id}>
                <div className="article-meta">
                  {t("聚合事件", "Clustered event")} · {e.article_count}{" "}
                  {t("篇报道", "articles")}
                </div>
                <h3>
                  <Link href={`/events/${e.id}`}>
                    <Highlight text={e.title_zh} query={filters.search} />
                  </Link>
                </h3>
                {e.summary_zh && (
                  <p className="article-summary">
                    <Highlight text={e.summary_zh} query={filters.search} />
                  </p>
                )}
                <Link className="source-link" href={`/events/${e.id}`}>
                  {t("查看事件报道", "Explore coverage")}
                  <ArrowUpRight size={12} />
                </Link>
              </article>
            ))
          )}
          {!!count && (
            <div className="pagination">
              <button
                className="btn btn-outline"
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                {t("上一页", "Previous")}
              </button>
              <span>
                {page} / {Math.ceil(count / 10)}
              </span>
              <button
                className="btn btn-outline"
                disabled={page * 10 >= count}
                onClick={() => setPage((p) => p + 1)}
              >
                {t("下一页", "Next")}
              </button>
            </div>
          )}
        </>
      )}
    </main>
  );
}
