"use client";
import Link from "next/link";
import { useState } from "react";
import {
  ArrowUpRight,
  TrendingUp,
  TrendingDown,
  Minus,
  Activity,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { publicApi } from "@/lib/api";
import { usePreferences } from "@/hooks/use-preferences";
import { SectionHeading } from "./section-heading";
import { PolicyCard } from "./policy-card";
import { Sparkline } from "./sparkline";
import { ReportArchive } from "./report-archive";
import { EmptyState, ErrorState, SkeletonCards } from "./ui/states";
import type { Insights, PolicyUpdate, PriceTrend } from "@/types";
export interface TrendData {
  hot?: Insights["hotspots"];
  alerts?: Insights["price_alerts"];
  policies?: PolicyUpdate[];
}
export function TrendWorkspace({ initial = {} }: { initial?: TrendData }) {
  const { t } = usePreferences();
  const [window, setWindow] = useState<"24h" | "48h" | "7d">("7d");
  const hot = useQuery({
    queryKey: ["hot-minerals", window],
    queryFn: () =>
      publicApi<Insights["hotspots"]>(`/trends/hot-minerals?window=${window}`),
    initialData: window === "7d" ? initial.hot : undefined,
    staleTime: 300000,
  });
  const alerts = useQuery({
    queryKey: ["price-alerts"],
    queryFn: () => publicApi<Insights["price_alerts"]>("/trends/price-alerts"),
    initialData: initial.alerts,
    staleTime: 60000,
    refetchInterval: 60000,
  });
  const prices = useQuery({
    queryKey: ["price-trends"],
    queryFn: () => publicApi<PriceTrend[]>("/trends/price-trends"),
    staleTime: 60000,
  });
  const policies = useQuery({
    queryKey: ["policy-updates"],
    queryFn: () => publicApi<PolicyUpdate[]>("/trends/policy-updates"),
    initialData: initial.policies,
    staleTime: 1800000,
  });
  return (
    <main className="workspace">
      <SectionHeading
        eyebrow="MARKET SIGNALS"
        zh="发现变化，读懂趋势。"
        en="Spot the change. Read the trend."
        description="用历史基线识别资讯热点，追踪真实报价与政策变化。"
        descriptionEn="Historical coverage baselines, comparable prices and policy developments."
      />
      <div className="section-bar flex-wrap gap-4">
        <h2>{t("热点矿种", "Trending minerals")}</h2>
        <div
          className="tabs"
          role="tablist"
          aria-label={t("热点统计窗口", "Coverage window")}
        >
          {(["24h", "48h", "7d"] as const).map((value) => (
            <button
              key={value}
              role="tab"
              aria-selected={window === value}
              className={window === value ? "active" : ""}
              onClick={() => setWindow(value)}
            >
              {value}
            </button>
          ))}
        </div>
      </div>
      <p className="text-xs text-muted mb-5">
        {t(
          "超过历史均值 2 倍标准差且至少 3 篇报道才标记为热点；历史样本不足时不判定异常。迷你图展示最近 7 天真实报道量。",
          "Hotspots require more than two historical standard deviations and at least 3 articles. Sparse history is not flagged. Sparklines show real 7-day coverage.",
        )}
      </p>
      {hot.isError ? (
        <ErrorState error={hot.error} retry={() => hot.refetch()} />
      ) : hot.isPending ? (
        <SkeletonCards />
      ) : hot.data?.length ? (
        <div className="directory-grid">
          {hot.data.map((x, i) => (
            <Link
              className="directory-card"
              href={`/minerals/${encodeURIComponent(x.mineral)}`}
              key={x.mineral}
              prefetch={false}
            >
              <div className="flex justify-between">
                <span className="eyebrow">
                  {String(i + 1).padStart(2, "0")} /{" "}
                  {x.is_hot ? "HOT SIGNAL" : "COVERAGE"}
                </span>
                {x.trend === "up" ? (
                  <TrendingUp size={20} className="text-green" />
                ) : x.trend === "down" ? (
                  <TrendingDown size={20} className="text-red" />
                ) : (
                  <Minus size={20} />
                )}
              </div>
              <h2 className="mt-5">{x.mineral}</h2>
              <div className="flex justify-between items-end mt-4">
                <div>
                  <strong className="text-3xl">{x.count}</strong>
                  <span className="text-sm text-muted ml-2">
                    {t("篇报道", "articles")}
                  </span>
                </div>
                <Sparkline
                  values={x.sparkline || []}
                  label={`${x.mineral} · ${t("最近七天报道量", "7-day coverage")}: ${(x.sparkline || []).join(", ")}`}
                />
              </div>
              <div className="flex justify-between mt-4 gap-2">
                <span className={`tag ${x.is_hot ? "signal-hot" : ""}`}>
                  {x.is_hot
                    ? t("热点", "Hotspot")
                    : !x.baseline_sufficient
                      ? t("历史样本不足", "Insufficient history")
                      : t("正常波动", "Normal variation")}
                </span>
                <span className="text-xs text-muted">
                  {t("热度", "Heat")}{" "}
                  {x.baseline_sufficient
                    ? `${x.heat_score.toFixed(0)}/100`
                    : "—"}
                </span>
              </div>
              <p className="text-muted text-xs mt-3">
                {t("前期报道", "Previous window")}: {x.previous_count} ·{" "}
                {x.growth_pct === null
                  ? t("无可比增幅", "No comparable growth")
                  : `${x.growth_pct > 0 ? "+" : ""}${x.growth_pct.toFixed(0)}%`}
              </p>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          title={t(
            "当前窗口暂无已发布报道",
            "No published coverage in this window",
          )}
        />
      )}
      <div className="grid lg:grid-cols-2 gap-6 mt-10">
        <section>
          <div className="section-bar">
            <h2>{t("价格异动", "Price warnings")}</h2>
            <span className="text-muted text-xs">
              {t("近 7 天 · 单日涨跌幅 >3%", "Past 7 days · daily moves >3%")}
            </span>
          </div>
          {alerts.isError ? (
            <ErrorState error={alerts.error} retry={() => alerts.refetch()} />
          ) : alerts.isPending ? (
            <SkeletonCards count={1} />
          ) : alerts.data?.length ? (
            <div className="panel">
              {alerts.data.map((x) => (
                <Link
                  className="insight-row"
                  href={`/minerals/${encodeURIComponent(x.mineral)}`}
                  key={x.id || `${x.mineral}-${x.date}-${x.source}`}
                >
                  <div>
                    <strong>{x.product || x.mineral}</strong>
                    <p className="text-muted text-xs mt-2">
                      {x.date} · {Number(x.price).toLocaleString()} {x.currency}
                      /{x.unit}
                    </p>
                    <p className="text-muted text-xs mt-1">{x.source}</p>
                  </div>
                  <div className="text-right">
                    <span
                      className={`alert-level alert-${x.severity || "green"}`}
                    >
                      {x.severity === "red"
                        ? t("高", "High")
                        : x.severity === "yellow"
                          ? t("中", "Medium")
                          : t("低", "Low")}
                    </span>
                    <strong className="block mt-2">
                      {Number(x.change_pct) > 0 ? "+" : ""}
                      {Number(x.change_pct).toFixed(2)}%
                    </strong>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              title={t(
                "尚无达到阈值的价格异动",
                "No daily warning exceeds the threshold",
              )}
              detail={t(
                "只比较同信源、产品、币种、单位的相邻日报价。",
                "Only consecutive-day quotes with the same source, product, currency and unit are compared.",
              )}
            />
          )}
        </section>
        <section>
          <div className="section-bar">
            <h2>{t("政策时间线", "Policy timeline")}</h2>
            <Link className="source-link" href="/policies">
              {t("全部政策", "All policies")}
              <ArrowUpRight size={12} />
            </Link>
          </div>
          {policies.isError ? (
            <ErrorState
              error={policies.error}
              retry={() => policies.refetch()}
            />
          ) : policies.isPending ? (
            <SkeletonCards count={1} />
          ) : policies.data?.length ? (
            <div className="timeline-list">
              {policies.data.map((p) => (
                <div className="timeline-group" key={p.id}>
                  <span className="text-muted text-xs">
                    {p.published_at
                      ? new Date(p.published_at).toLocaleDateString("en-CA", {
                          timeZone: "Asia/Shanghai",
                        })
                      : "—"}{" "}
                    · {p.region || p.country}
                  </span>
                  <div className="flex flex-wrap gap-2 my-3">
                    {p.themes?.map((theme) => (
                      <span className="tag" key={theme}>
                        {theme}
                      </span>
                    ))}
                  </div>
                  <PolicyCard policy={p} />
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title={t(
                "近一周暂无政策更新",
                "No policy updates in the last week",
              )}
            />
          )}
        </section>
      </div>
      <section className="mt-10">
        <div className="section-bar">
          <h2 className="flex gap-2 items-center">
            <Activity size={18} />
            {t("连续报价趋势", "Consecutive quoted movements")}
          </h2>
        </div>
        {prices.isError ? (
          <ErrorState error={prices.error} retry={() => prices.refetch()} />
        ) : prices.isPending ? (
          <SkeletonCards count={1} />
        ) : prices.data?.length ? (
          <div className="policy-grid">
            {prices.data.map((x) => (
              <Link
                className="policy-card"
                href={`/minerals/${encodeURIComponent(x.mineral)}`}
                key={x.id}
              >
                <div className="flex justify-between gap-3">
                  <h3>{x.product || x.mineral}</h3>
                  <span className="tag">
                    {x.direction === "up"
                      ? t("上涨", "Up")
                      : x.direction === "down"
                        ? t("下跌", "Down")
                        : t("持平", "Flat")}
                  </span>
                </div>
                <div className="flex justify-between mt-4">
                  <strong>
                    {Number(x.price).toLocaleString()} {x.currency}/{x.unit}
                  </strong>
                  <Sparkline
                    values={x.observations.map((o) => Number(o.price))}
                    label={`${x.mineral} ${t("原始报价走势", "observed prices")}`}
                  />
                </div>
                <p className="text-muted text-xs mt-3">
                  {x.consecutive_moves}{" "}
                  {t("次连续同向变动", "consecutive quoted moves")} · {x.source}{" "}
                  · {x.date}
                </p>
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState
            title={t(
              "最近七天暂无真实报价",
              "No real quotes in the last seven days",
            )}
          />
        )}
      </section>
      <ReportArchive />
    </main>
  );
}
