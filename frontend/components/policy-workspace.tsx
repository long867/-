"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { LayoutGrid, List, ChevronLeft, ChevronRight } from "lucide-react";
import { publicApi } from "@/lib/api";
import { useUrlFilters } from "@/hooks/use-url-filters";
import { usePreferences } from "@/hooks/use-preferences";
import { SectionHeading } from "./section-heading";
import { PolicyCard } from "./policy-card";
import { EmptyState, ErrorState, SkeletonCards } from "./ui/states";
import type { Facets, PolicyPage } from "@/types";
export function PolicyWorkspace({ initial }: { initial?: PolicyPage }) {
  const { t } = usePreferences();
  const { filters, update, ready } = useUrlFilters();
  const [page, setPage] = useState(1);
  const [timeline, setTimeline] = useState(false);
  const facets = useQuery({
    queryKey: ["facets"],
    queryFn: () => publicApi<Facets>("/facets"),
    staleTime: 300000,
  });
  const params = new URLSearchParams({ page: String(page), page_size: "12" });
  params.set("date_basis", "published_at");
  if (filters.regions[0]) params.set("region", filters.regions[0]);
  if (filters.minerals[0]) params.set("mineral", filters.minerals[0]);
  for (const k of ["date_from", "date_to"] as const)
    if (filters[k]) params.set(k, filters[k]);
  const result = useQuery({
    queryKey: ["policies", params.toString()],
    queryFn: () => publicApi<PolicyPage>(`/policies?${params}`),
    enabled: ready,
    initialData:
      !filters.regions.length &&
      !filters.minerals.length &&
      !filters.date_from &&
      !filters.date_to &&
      page === 1
        ? initial
        : undefined,
  });
  function change(values: Parameters<typeof update>[0]) {
    setPage(1);
    update(values);
  }
  return (
    <main className="workspace">
      <SectionHeading
        eyebrow="POLICY INTELLIGENCE"
        zh="政策，决定下一步。"
        en="Policy shapes the next move."
        description="追踪关键矿产监管与产业政策，直接查阅原始文件。"
        descriptionEn="Track mineral regulation and industrial policy, with original documents."
      />
      <div className="filter-panel">
        <div className="filter-toolbar">
          <select
            aria-label={t("政策地区", "Policy region")}
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
            aria-label={t("政策矿种", "Policy mineral")}
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
          <label className="date-filter">
            {t("发布日期起", "Published from")}
            <input
              type="date"
              value={filters.date_from}
              onChange={(e) => change({ date_from: e.target.value })}
            />
          </label>
          <label className="date-filter">
            {t("发布日期止", "Published to")}
            <input
              type="date"
              value={filters.date_to}
              onChange={(e) => change({ date_to: e.target.value })}
            />
          </label>
          <button
            className="btn btn-outline"
            onClick={() => setTimeline(!timeline)}
          >
            {timeline ? <LayoutGrid size={14} /> : <List size={14} />}{" "}
            {t(
              timeline ? "卡片视图" : "时间线视图",
              timeline ? "Cards" : "Timeline",
            )}
          </button>
        </div>
      </div>
      <div className="section-bar">
        <h2>{t("政策法规", "Policy & regulation")}</h2>
        <span className="text-muted text-sm">
          {result.data?.total ?? "—"} {t("份文件", "documents")}
        </span>
      </div>
      {result.isError ? (
        <ErrorState error={result.error} retry={() => result.refetch()} />
      ) : result.isPending ? (
        <SkeletonCards />
      ) : result.data?.items.length ? (
        <div className={timeline ? "timeline-list" : "policy-grid"}>
          {result.data.items.map((p) => (
            <div key={p.id} className={timeline ? "timeline-group" : ""}>
              {timeline && (
                <div className="timeline-date">
                  {p.published_at
                    ? new Date(p.published_at).toLocaleDateString("zh-CN", {
                        timeZone: "Asia/Shanghai",
                      })
                    : t("发布日期未披露", "Publication date not specified")}
                </div>
              )}
              <PolicyCard policy={p} />
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          title={t("暂无符合条件的政策", "No policies match these filters")}
          detail={t(
            "政策文件通过采集、加工与审核后在此展示。",
            "Policy documents appear here after ingestion, processing and review.",
          )}
        />
      )}
      <div className="pagination">
        <button
          className="btn btn-outline"
          disabled={page === 1}
          onClick={() => setPage((p) => p - 1)}
          aria-label={t("上一页", "Previous page")}
        >
          <ChevronLeft size={16} />
        </button>
        <span>
          {page} / {Math.max(1, Math.ceil((result.data?.total || 0) / 12))}
        </span>
        <button
          className="btn btn-outline"
          disabled={!result.data || page * 12 >= result.data.total}
          onClick={() => setPage((p) => p + 1)}
          aria-label={t("下一页", "Next page")}
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </main>
  );
}
