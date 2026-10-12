"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  CalendarDays,
  Newspaper,
  Globe2,
  Layers3,
} from "lucide-react";
import { publicApi } from "@/lib/api";
import { usePreferences } from "@/hooks/use-preferences";
import { SectionHeading } from "./section-heading";
import { EmptyState, ErrorState, SkeletonCards } from "./ui/states";
import type { Digest } from "@/types";
import { ReportArchive } from "./report-archive";
import { ReportAnalysis } from "./report-analysis";
const Chart = dynamic(() => import("./digest-chart"), {
  ssr: false,
  loading: () => <div className="skeleton h-60" />,
});
export function DigestWorkspace({ initial }: { initial?: Digest }) {
  const { t } = usePreferences();
  const [kind, setKind] = useState<Digest["kind"]>("daily");
  const [reportId, setReportId] = useState<string | null>(null);
  const [scope, setScope] = useState<"current" | "previous" | "latest">(
    "latest",
  );
  useEffect(() => {
    const sync = () => {
      const k = new URLSearchParams(location.search).get("kind");
      setKind(k === "weekly" || k === "monthly" ? k : "daily");
      setReportId(new URLSearchParams(location.search).get("report"));
      setScope(
        new URLSearchParams(location.search).get("scope") === "current"
          ? "current"
          : new URLSearchParams(location.search).get("scope") === "previous"
            ? "previous"
            : "latest",
      );
    };
    sync();
    addEventListener("popstate", sync);
    return () => removeEventListener("popstate", sync);
  }, []);
  const query = useQuery({
    queryKey: ["digest", kind, reportId, scope],
    queryFn: () =>
      publicApi<Digest>(
        reportId
          ? `/digest/reports/${encodeURIComponent(reportId)}`
          : `/digest/${kind}?scope=${scope}`,
      ),
    initialData:
      kind === "daily" && !reportId && scope === "latest" ? initial : undefined,
    staleTime: 3600000,
  });
  const d = query.data;
  return (
    <main className="workspace">
      <SectionHeading
        eyebrow="THE INTELLIGENCE BRIEF"
        zh="每日情报，清晰可读。"
        en="Your intelligence, distilled."
        description="从已发布资讯生成摘要与统计，每条引用都能追溯。"
        descriptionEn="Digests and statistics from published coverage, with traceable evidence."
      />
      <div
        className="tabs mb-7"
        role="tablist"
        aria-label={t("简报周期", "Digest period")}
      >
        {(
          [
            ["daily", "日报", "Daily"],
            ["weekly", "周报", "Weekly"],
            ["monthly", "月报", "Monthly"],
          ] as const
        ).map(([k, zh, en]) => (
          <button
            role="tab"
            aria-selected={kind === k}
            className={kind === k ? "active" : ""}
            key={k}
            onClick={() => {
              setKind(k);
              setReportId(null);
              history.replaceState(
                null,
                "",
                `${location.pathname}?kind=${k}&scope=${scope}`,
              );
            }}
          >
            {t(zh, en)}
          </button>
        ))}
      </div>
      <div className="tabs mb-7" aria-label={t("报告范围", "Report scope")}>
        {(["latest", "previous", "current"] as const).map((value) => (
          <button
            key={value}
            className={!reportId && scope === value ? "active" : ""}
            onClick={() => {
              setScope(value);
              setReportId(null);
              history.replaceState(
                null,
                "",
                `${location.pathname}?kind=${kind}&scope=${value}`,
              );
            }}
          >
            {value === "latest"
              ? t("最新有资料的周期", "Latest covered period")
              : value === "previous"
                ? t("上一完整周期", "Previous complete period")
                : t("本期实时简报", "Current live digest")}
          </button>
        ))}
      </div>
      {query.isError ? (
        <ErrorState error={query.error} retry={() => query.refetch()} />
      ) : query.isPending ? (
        <SkeletonCards />
      ) : (
        d && (
          <>
            <h2 className="text-xl mb-5">{d.title}</h2>
            <div className="panel mb-5 flex flex-wrap items-center justify-between gap-4">
              <p className="text-sm text-muted">
                {t(
                  "按资料实际发布日期统计，历史资料不会标为今日新闻。",
                  "Coverage follows actual publication dates.",
                )}
              </p>
              <Link
                className="btn btn-outline"
                href="/research"
                prefetch={false}
              >
                {t(
                  "分析可能影响与应对措施",
                  "Explore implications and actions",
                )}
              </Link>
            </div>
            <div className="flex flex-wrap justify-between gap-3 text-xs text-muted mb-5">
              <span className="inline-flex gap-2 items-center">
                <CalendarDays size={14} />
                {d.period_start} — {d.period_end} (
                {t("结束日不含", "end exclusive")}) · {d.timezone}
              </span>
              <span>
                {d.mode === "llm"
                  ? t("AI 摘要 · 附原文依据", "AI digest · original evidence")
                  : d.mode === "extractive"
                    ? t("原文摘录摘要", "Extractive digest")
                    : t("本期尚无资料", "No coverage in this period")}
              </span>
            </div>
            {(reportId || d.scheduled) && (
              <div className="tag mb-5">{t("归档报告", "Archived report")}</div>
            )}
            <div className="metric-grid mb-7">
              {[
                [
                  Newspaper,
                  d.stats.article_count,
                  t("已发布文章", "Published articles"),
                ],
                [Globe2, d.stats.source_count, t("独立信源", "Sources")],
                [
                  Layers3,
                  Object.keys(d.stats.minerals).length,
                  t("覆盖矿种", "Minerals"),
                ],
              ].map(([Icon, n, label]) => {
                const I = Icon as typeof Newspaper;
                return (
                  <div className="metric-card" key={String(label)}>
                    <I size={17} className="text-accent" />
                    <strong>{n as number}</strong>
                    <span>{label as string}</span>
                  </div>
                );
              })}
            </div>
            {d.mode === "empty" ? (
              <EmptyState
                title={t(
                  "本期尚无已发布资讯",
                  "No published coverage for this period",
                )}
                detail={t(
                  "可切换周报或月报查看已有资料。",
                  "Switch to weekly or monthly to explore existing coverage.",
                )}
              />
            ) : (
              <div className="digest-layout">
                <article className="panel digest-prose">
                  <div className="whitespace-pre-wrap leading-8 mt-6">
                    {d.content.split(/(\[\d+\])/).map((part, i) => {
                      const n = /^\[(\d+)\]$/.exec(part);
                      return n ? (
                        <a
                          className="citation-link"
                          key={i}
                          href={`#digest-source-${n[1]}`}
                        >
                          {part}
                        </a>
                      ) : (
                        <span key={i}>{part}</span>
                      );
                    })}
                  </div>
                </article>
                <aside className="panel h-fit">
                  <h2 className="mb-5">{t("矿种覆盖", "Mineral coverage")}</h2>
                  <Chart minerals={d.stats.minerals} />
                  <p className="text-xs text-muted mt-3">
                    {t(
                      "一篇文章可能覆盖多个矿种。",
                      "An article can cover multiple minerals.",
                    )}
                  </p>
                </aside>
              </div>
            )}{" "}
            <ReportAnalysis report={d} />
            {!!d.sources.length && (
              <section className="mt-10">
                <div className="section-bar">
                  <h2>{t("重点文章与证据", "Coverage & evidence")}</h2>
                  <span className="text-xs text-muted">{d.sources.length}</span>
                </div>
                <div className="policy-grid">
                  {d.sources.map((s, i) => (
                    <article
                      className="policy-card scroll-mt-24"
                      id={`digest-source-${i + 1}`}
                      key={s.article_id}
                    >
                      <div className="article-meta">
                        <span className="text-accent">[{i + 1}]</span>
                        <span>{s.source_name}</span>
                        <span>
                          {s.published_at
                            ? new Date(s.published_at).toLocaleDateString(
                                "en-CA",
                                { timeZone: "Asia/Shanghai" },
                              )
                            : "—"}
                        </span>
                      </div>
                      <h3 className="text-base leading-7 my-3">
                        <Link href={`/articles/${s.article_id}`}>
                          {s.title}
                        </Link>
                      </h3>
                      <p>{s.snippet}</p>
                      <a
                        className="source-link"
                        href={s.url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {t("查看原文", "Original source")}
                        <ArrowUpRight size={12} />
                      </a>
                    </article>
                  ))}
                </div>
              </section>
            )}
          </>
        )
      )}
      <ReportArchive
        key={kind}
        kind={kind}
        select={(report) => {
          setKind(report.kind);
          setReportId(report.id || null);
          setScope("previous");
          history.replaceState(
            null,
            "",
            `${location.pathname}?kind=${report.kind}&report=${report.id}`,
          );
          window.scrollTo({ top: 0, behavior: "smooth" });
        }}
      />
    </main>
  );
}
