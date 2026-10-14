"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Atom,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  FlaskConical,
  Globe2,
  Layers3,
  Search,
} from "lucide-react";
import { publicApi } from "@/lib/api";
import { frontierFilters, frontierParams } from "@/lib/frontier";
import { usePreferences } from "@/hooks/use-preferences";
import { EmptyState, ErrorState, SkeletonCards } from "./ui/states";
import type {
  FrontierFilters,
  FrontierPage,
  FrontierPaper,
} from "@/types/frontier";

function PaperCard({
  paper,
  featured,
  labels,
}: {
  paper: FrontierPaper;
  featured: boolean;
  labels: Record<string, string>;
}) {
  const { t, language } = usePreferences();
  return (
    <article
      className={`frontier-paper ${featured ? "frontier-featured" : ""}`}
    >
      <div className="frontier-paper-meta">
        <span>
          <BookOpen size={13} />
          {t("期刊论文", "Journal article")}
        </span>
        <time dateTime={paper.published_date || undefined}>
          {paper.published_date || t("日期未披露", "Date unavailable")}
        </time>
      </div>
      <div className="frontier-paper-journal">{paper.journal}</div>
      <Link
        href={`/articles/${paper.id}`}
        prefetch={false}
        className="frontier-paper-title"
      >
        <h2>
          {language === "zh" ? paper.title_zh || paper.title : paper.title}
        </h2>
        <ArrowUpRight size={18} />
      </Link>
      {language === "zh" && paper.title_zh && (
        <p className="frontier-original-title" lang="en">
          {paper.title}
        </p>
      )}
      <div className="frontier-evidence-label">
        <FlaskConical size={13} />
        {paper.abstract_available
          ? t("基于公开摘要整理", "Public abstract available")
          : t(
              "题录速览 · 摘要暂未公开",
              "Bibliographic record · abstract unavailable",
            )}
      </div>
      <p className="frontier-paper-summary">
        {paper.summary_zh ||
          t(
            "中文摘要正在加工，请先查看原始论文题录。",
            "Chinese digest is being prepared. Open the original record.",
          )}
      </p>
      <div className="frontier-paper-tags">
        {paper.directions.map((key) => (
          <span key={key}>{labels[key] || key}</span>
        ))}
        {paper.minerals.map((name) => (
          <Link
            key={name}
            href={`/minerals/${encodeURIComponent(name)}`}
            prefetch={false}
          >
            {name}
          </Link>
        ))}
      </div>
      <div className="frontier-authors">
        {paper.authors.length ? (
          <>
            <span>{t("作者", "Authors")}</span>{" "}
            {paper.authors.slice(0, 3).join(" · ")}
            {paper.authors.length > 3 ? t(" 等", " et al.") : ""}
          </>
        ) : (
          t("作者信息未提供", "Authors not provided")
        )}
      </div>
      {!!paper.institutions.length && (
        <p className="frontier-institutions">
          {paper.institutions.slice(0, 2).join(" · ")}
        </p>
      )}
      <footer>
        <span title={paper.doi}>DOI · {paper.doi}</span>
        <a href={paper.url} target="_blank" rel="noopener noreferrer">
          {t("期刊原文", "Original paper")}
          <ArrowUpRight size={14} />
        </a>
      </footer>
    </article>
  );
}

export function FrontierWorkspace({
  initial,
  initialFilters,
}: {
  initial?: FrontierPage;
  initialFilters: FrontierFilters;
}) {
  const { t, language } = usePreferences();
  const [filters, setFilters] = useState(initialFilters);
  const [keyword, setKeyword] = useState(initialFilters.search);
  const params = frontierParams(filters);
  const query = useQuery({
    queryKey: ["frontier", params],
    queryFn: () => publicApi<FrontierPage>(`/frontier?${params}`),
    initialData:
      params === frontierParams(initialFilters) ? initial : undefined,
    placeholderData: keepPreviousData,
    staleTime: 300000,
  });
  useEffect(() => {
    function restore() {
      const next = frontierFilters(
        Object.fromEntries(new URLSearchParams(window.location.search)),
      );
      setFilters(next);
      setKeyword(next.search);
    }
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, []);
  function update(values: Partial<FrontierFilters>) {
    const next = { ...filters, page: 1, ...values };
    setFilters(next);
    window.history.pushState(null, "", `/frontier?${frontierParams(next)}`);
  }
  const data = query.data;
  const overview = data?.overview;
  const labels = Object.fromEntries(
    (overview?.directions || []).map((row) => [
      row.key,
      language === "zh" ? row.name : row.english_name,
    ]),
  );
  const metrics = [
    [overview?.total, t("已收录论文", "Papers tracked")],
    [overview?.recent_30_days, t("近30天发布", "Published in 30 days")],
    [overview?.abstract_count, t("可读公开摘要", "Available abstracts")],
    [overview?.journal_count, t("已覆盖期刊", "Journals covered")],
  ];
  return (
    <main className="workspace frontier-workspace">
      <section className="frontier-hero">
        <div className="frontier-hero-copy">
          <div className="eyebrow">RESEARCH FRONTIERS / 矿产研究观察</div>
          <h1>
            {t("前沿成果", "Research frontiers")}
            <span>
              {t(
                "从研究前沿，看见资源未来。",
                "Discover the science shaping resources.",
              )}
            </span>
          </h1>
          <p>
            {t(
              "追踪全球矿产资源相关研究，把新的问题、方法与发现，整理成可读、可追溯的中文资料。",
              "Track mineral resource research with readable Chinese digests and traceable original papers.",
            )}
          </p>
          <div className="frontier-hero-badges">
            <span>
              <Globe2 size={14} />
              {t("公开可读", "Public access")}
            </span>
            <span>
              <span className="status-dot" />
              {t("每日追踪", "Daily tracking")}
            </span>
            <span>
              <Layers3 size={14} />
              {t("科研与社科视角", "Science & society")}
            </span>
          </div>
        </div>
        <div className="frontier-orbit" aria-hidden="true">
          <div className="frontier-orbit-ring" />
          <div className="frontier-orbit-ring frontier-ring-two" />
          <div className="frontier-orbit-ring frontier-ring-three" />
          <div className="frontier-orbit-core">
            <Atom size={51} strokeWidth={1} />
            <span>
              MINERAL
              <br />
              RESEARCH
            </span>
          </div>
          <span className="frontier-orbit-point point-one">
            {t("成矿勘探", "EXPLORATION")}
          </span>
          <span className="frontier-orbit-point point-two">
            {t("绿色回收", "CIRCULARITY")}
          </span>
          <span className="frontier-orbit-point point-three">
            {t("资源治理", "GOVERNANCE")}
          </span>
        </div>
      </section>
      <section
        className="frontier-metrics"
        aria-label={t("真实收录统计", "Actual publication coverage")}
      >
        {metrics.map(([value, label]) => (
          <div key={String(label)}>
            <strong>{value ?? "—"}</strong>
            <span>{label}</span>
          </div>
        ))}
      </section>
      <section
        className="frontier-controls panel"
        aria-label={t("研究成果筛选", "Filter research")}
      >
        <div className="frontier-direction-list">
          <button
            className={!filters.direction ? "selected" : ""}
            aria-pressed={!filters.direction}
            onClick={() => update({ direction: "" })}
          >
            {t("全部方向", "All directions")}
          </button>
          {overview?.directions.map((row) => (
            <button
              key={row.key}
              className={filters.direction === row.key ? "selected" : ""}
              aria-pressed={filters.direction === row.key}
              onClick={() => update({ direction: row.key })}
            >
              {labels[row.key]}
              <small>{row.count}</small>
            </button>
          ))}
        </div>
        <div className="frontier-filter-row">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              update({ search: keyword.trim() });
            }}
          >
            <Search size={16} />
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              maxLength={200}
              placeholder={t(
                "搜索研究主题、作者、期刊或 DOI",
                "Topic, author, journal or DOI",
              )}
              aria-label={t("搜索研究成果", "Search research")}
            />
            <button type="submit">{t("搜索", "Search")}</button>
          </form>
          <label>
            <span>{t("矿种", "Mineral")}</span>
            <select
              value={filters.mineral}
              onChange={(event) => update({ mineral: event.target.value })}
            >
              <option value="">{t("全部矿种", "All minerals")}</option>
              {overview?.minerals.map((row) => (
                <option value={row.name} key={row.name}>
                  {row.name} ({row.count})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{t("时间", "Period")}</span>
            <select
              value={filters.days}
              onChange={(event) => update({ days: Number(event.target.value) })}
            >
              {[7, 30, 90, 365].map((days) => (
                <option key={days} value={days}>
                  {t(`近${days}天`, `Past ${days} days`)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>
      <div className="frontier-content">
        <section aria-busy={query.isFetching}>
          <div className="frontier-result-heading">
            <h2>
              {t("最新研究", "Latest publications")}{" "}
              <span>{data?.total ?? "—"}</span>
            </h2>
            <span>
              {query.isFetching
                ? t("正在更新…", "Updating…")
                : t("按发表时间排序", "Newest first")}
            </span>
          </div>
          {query.isError ? (
            <ErrorState error={query.error} retry={() => query.refetch()} />
          ) : query.isPending ? (
            <SkeletonCards count={4} />
          ) : !data?.items.length ? (
            <EmptyState
              title={t("当前筛选下暂无成果", "No papers match these filters")}
              detail={t(
                "可扩大时间范围或切换研究方向。系统持续补充真实研究资料。",
                "Try a wider period or another direction. Actual research records are being added.",
              )}
            />
          ) : (
            <div
              className={`frontier-paper-grid ${query.isPlaceholderData ? "is-updating" : ""}`}
            >
              {data.items.map((paper, index) => (
                <PaperCard
                  key={paper.id}
                  paper={paper}
                  featured={filters.page === 1 && index === 0}
                  labels={labels}
                />
              ))}
            </div>
          )}
          {data && data.total > data.page_size && (
            <div className="frontier-pagination">
              <button
                disabled={filters.page === 1 || query.isFetching}
                onClick={() => update({ page: filters.page - 1 })}
              >
                <ChevronLeft size={16} />
                {t("上一页", "Previous")}
              </button>
              <span>
                {filters.page} / {Math.ceil(data.total / data.page_size)}
              </span>
              <button
                disabled={!data.has_more || query.isFetching}
                onClick={() => update({ page: filters.page + 1 })}
              >
                {t("下一页", "Next")}
                <ChevronRight size={16} />
              </button>
            </div>
          )}
        </section>
        <aside className="frontier-sidebar">
          <div className="panel">
            <div className="eyebrow">SOURCE & METHOD</div>
            <h2>{t("让成果有据可查", "Trace the original research")}</h2>
            <p>
              {t(
                "来自公开学术题录与已提供的摘要。每条资料保留作者、期刊、发表日期与 DOI，点击即可到原始发表页面。",
                "Public scholarly metadata and deposited abstracts, with authors, journals, dates and DOI links.",
              )}
            </p>
            <div className="frontier-method-item">
              <FlaskConical size={17} />
              <div>
                <strong>
                  {t("摘要与题录分开展示", "Clear evidence scope")}
                </strong>
                <p>
                  {t(
                    "有摘要时整理研究内容；缺少摘要时仅展示题录，不推测研究结论。",
                    "Abstract digests and title-only records are clearly distinguished.",
                  )}
                </p>
              </div>
            </div>
            <div className="frontier-method-item">
              <BookOpen size={17} />
              <div>
                <strong>
                  {t("研究进展 ≠ 产业化结果", "Research and application")}
                </strong>
                <p>
                  {t(
                    "实验条件、适用范围和实际应用仍需核对原文。",
                    "Check experimental conditions and application limits in the original paper.",
                  )}
                </p>
              </div>
            </div>
            <div className="frontier-update">
              <span>{t("最近成功采集", "Last successful collection")}</span>
              <strong>
                {overview?.last_collected_at
                  ? new Date(overview.last_collected_at).toLocaleString(
                      language === "zh" ? "zh-CN" : "en-GB",
                      {
                        timeZone: "Asia/Shanghai",
                        month: "2-digit",
                        day: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      },
                    )
                  : t("首批资料整理中", "Initial collection in progress")}
              </strong>
              <small>
                {t(
                  "北京时间 · 每24小时采集",
                  "China time · collected every 24 hours",
                )}
              </small>
            </div>
          </div>
          <div className="panel frontier-ask">
            <Atom size={24} />
            <h2>{t("继续深入研究", "Explore further")}</h2>
            <p>
              {t(
                "把研究问题带给矿眸智探，结合已收录资料分析技术路径与资源影响。",
                "Ask the assistant to analyze research paths using the collected evidence.",
              )}
            </p>
            <Link href="/chat" prefetch={false}>
              {t("向矿眸智探提问", "Ask the assistant")}
              <ArrowUpRight size={16} />
            </Link>
          </div>
        </aside>
      </div>
    </main>
  );
}
