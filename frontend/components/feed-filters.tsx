"use client";
import { Search, SlidersHorizontal, X, ChevronDown } from "lucide-react";
import { useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { usePreferences } from "@/hooks/use-preferences";
import { publicApi } from "@/lib/api";
import { emptyFilters, type FeedFilters } from "@/hooks/use-url-filters";
import type { Facets } from "@/types";
export function FeedFiltersBar({
  filters,
  update,
  initialFacets,
  compact = false,
}: {
  filters: FeedFilters;
  update: (changes: Partial<FeedFilters>) => void;
  initialFacets?: Facets;
  compact?: boolean;
}) {
  const { t } = usePreferences();
  const [expanded, setExpanded] = useState(false);
  const filterId = useId();
  const facets = useQuery({
    queryKey: ["facets"],
    queryFn: () => publicApi<Facets>("/facets"),
    initialData: initialFacets,
    staleTime: 300000,
  });
  const active =
    filters.minerals.length +
    filters.regions.length +
    filters.tags.length +
    (filters.category ? 1 : 0) +
    (filters.search ? 1 : 0) +
    (filters.company ? 1 : 0) +
    (filters.date_from ? 1 : 0) +
    (filters.date_to ? 1 : 0);
  return (
    <div
      className={`filter-panel feed-filter-panel ${expanded ? "filters-expanded" : ""}`}
    >
      <div className="mobile-filter-heading">
        <span>{t("筛选情报", "Filter coverage")}</span>
        <button
          type="button"
          className="mobile-filter-toggle"
          aria-expanded={expanded}
          aria-controls={
            compact
              ? `${filterId}-dates`
              : `${filterId}-regions ${filterId}-tags ${filterId}-dates`
          }
          onClick={() => setExpanded((value) => !value)}
        >
          <SlidersHorizontal size={15} />
          {t(
            expanded ? "收起筛选" : "更多筛选",
            expanded ? "Less" : "More filters",
          )}
          {active > 0 && <span className="filter-active-count">{active}</span>}
          <ChevronDown size={14} className={expanded ? "rotate-180" : ""} />
        </button>
      </div>
      {active > 0 && (
        <p className="mobile-filter-selection">
          {t("已选", "Selected")}:{" "}
          {[
            ...filters.minerals,
            ...filters.regions,
            ...filters.tags,
            filters.company,
            filters.search,
            filters.category,
            filters.date_from,
            filters.date_to,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
      )}
      {!compact &&
        (
          [
            ["minerals", t("矿种", "Mineral")],
            ["regions", t("地区", "Region")],
            ["tags", t("主题", "Topic")],
          ] as const
        ).map(([key, label]) => (
          <div
            className={`filter-row filter-row-${key}`}
            id={`${filterId}-${key}`}
            key={key}
          >
            <span className="filter-caption">{label}</span>
            <div className="chips">
              <button
                className={`chip ${filters[key].length === 0 ? "selected" : ""}`}
                aria-pressed={filters[key].length === 0}
                onClick={() => update({ [key]: [] })}
              >
                {t("全部", "All")}
              </button>
              {facets.data?.[key]
                .slice(0, key === "tags" ? 9 : 14)
                .map((item) => (
                  <button
                    key={item.name}
                    className={`chip ${filters[key].includes(item.name) ? "selected" : ""}`}
                    aria-pressed={filters[key].includes(item.name)}
                    onClick={() =>
                      update({
                        [key]: filters[key].includes(item.name)
                          ? filters[key].filter((name) => name !== item.name)
                          : [...filters[key], item.name].slice(0, 20),
                      })
                    }
                  >
                    {item.name}
                    <span className="chip-count">{item.count}</span>
                  </button>
                ))}
            </div>
          </div>
        ))}
      {filters.company && (
        <div className="filter-row filter-row-company">
          <span className="filter-caption">{t("公司", "Company")}</span>
          <button
            className="chip selected"
            onClick={() => update({ company: "" })}
          >
            {filters.company}
            <X size={11} />
          </button>
        </div>
      )}
      <div className="filter-tools">
        <div className="search-field">
          <Search size={14} />
          <input
            aria-label={t("搜索资讯", "Search intelligence")}
            placeholder={t(
              "矿种、公司、项目或关键词…",
              "Commodity, company, project or keyword…",
            )}
            value={filters.search}
            maxLength={200}
            onChange={(e) => update({ search: e.target.value })}
          />
        </div>
        <select
          value={filters.category}
          aria-label={t("资讯类型", "Article type")}
          onChange={(e) => update({ category: e.target.value })}
        >
          <option value="">{t("全部类型", "All types")}</option>
          {[
            ["news", "新闻", "News"],
            ["price", "价格", "Price"],
            ["policy", "政策", "Policy"],
            ["report", "研报", "Research"],
            ["company", "公告", "Company"],
          ].map(([v, zh, en]) => (
            <option key={v} value={v}>
              {t(zh, en)}
            </option>
          ))}
        </select>
        <select
          aria-label={t("文章排序", "Sort articles")}
          value={filters.sort_by}
          onChange={(e) => update({ sort_by: e.target.value })}
        >
          <option value="published_at">{t("最新发布", "Newest first")}</option>
          <option value="quality_score">
            {t("质量优先", "Highest quality")}
          </option>
        </select>
        <div className="filter-date-fields" id={`${filterId}-dates`}>
          <label className="text-[10px] text-muted">
            {t("从", "From")}{" "}
            <input
              type="date"
              aria-label={t("开始日期（UTC）", "Start date (UTC)")}
              value={filters.date_from}
              onChange={(e) => update({ date_from: e.target.value })}
            />
          </label>
          <label className="text-[10px] text-muted">
            {t("至", "To")}{" "}
            <input
              type="date"
              aria-label={t("结束日期（UTC）", "End date (UTC)")}
              value={filters.date_to}
              onChange={(e) => update({ date_to: e.target.value })}
            />
          </label>
        </div>
        {active > 0 ? (
          <button
            className="icon-button"
            onClick={() => update(emptyFilters)}
            aria-label={t("清除筛选", "Clear filters")}
          >
            <X size={14} />
          </button>
        ) : (
          <SlidersHorizontal size={13} className="text-muted" />
        )}
      </div>
    </div>
  );
}
