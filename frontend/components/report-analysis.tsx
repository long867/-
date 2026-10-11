"use client";
import Link from "next/link";
import dynamic from "next/dynamic";
import { usePreferences } from "@/hooks/use-preferences";
import { PolicyCard } from "./policy-card";
import type { Digest } from "@/types";
const CoverageChart = dynamic(() => import("./report-chart"), {
  ssr: false,
  loading: () => <div className="skeleton h-60" />,
});
const PriceChart = dynamic(
  () => import("./price-chart").then((x) => x.PriceChart),
  { ssr: false, loading: () => <div className="skeleton h-60" /> },
);

export function ReportAnalysis({ report }: { report: Digest }) {
  const { t } = usePreferences();
  const data = report.analysis;
  if (!data || !Object.keys(data).length) return null;
  return (
    <section className="mt-10 report-analysis">
      <div className="section-bar">
        <h2>{t("本期趋势与事件", "Period insights & events")}</h2>
        <span className="text-xs text-muted">
          {t(
            "统计和图表来自原始记录",
            "Statistics and charts from original records",
          )}
        </span>
      </div>
      <div className="grid md:grid-cols-2 gap-6">
        <div className="panel">
          <h3>{t("本期报道矿种 Top 5", "Top 5 minerals by coverage")}</h3>
          {data.hot_minerals?.length ? (
            data.hot_minerals.map((x) => (
              <Link
                className="insight-row"
                key={x.mineral}
                href={`/minerals/${encodeURIComponent(x.mineral)}`}
              >
                <span>{x.mineral}</span>
                <strong>
                  {x.count} {t("篇", "articles")}
                </strong>
              </Link>
            ))
          ) : (
            <p className="text-muted mt-4">
              {t("本期暂无报道", "No coverage in this period")}
            </p>
          )}
          <p className="text-xs text-muted mt-4">
            {t(
              "报道数量表示资讯活跃度，不等于市场价格或投资趋势。",
              "Coverage measures news activity, not prices or investment direction.",
            )}
          </p>
        </div>
        {!!data.coverage_by_day?.length && (
          <div className="panel">
            <h3 className="mb-4">{t("每日报道量", "Daily coverage")}</h3>
            <CoverageChart data={data.coverage_by_day} />
          </div>
        )}
      </div>
      {!!data.price_series?.length && (
        <div className="panel mt-6">
          <h3 className="mb-4">
            {t("本期价格走势", "Observed period prices")}
          </h3>
          <PriceChart prices={data.price_series} />
        </div>
      )}
      <div className="grid md:grid-cols-2 gap-6 mt-6">
        <div className="panel">
          <h3>{t("价格异动", "Price warnings")}</h3>
          {data.price_alerts?.length ? (
            data.price_alerts.map((x) => (
              <Link
                key={x.id}
                className="insight-row"
                href={`/minerals/${encodeURIComponent(x.mineral)}`}
              >
                <span>
                  {x.mineral} · {x.date}
                </span>
                <strong>
                  {Number(x.change_pct) > 0 ? "+" : ""}
                  {x.change_pct}%
                </strong>
              </Link>
            ))
          ) : (
            <p className="text-muted mt-4">
              {t(
                "本期暂无符合日涨跌幅 >3% 的记录",
                "No daily movement above 3% in this period",
              )}
            </p>
          )}
        </div>
        <div className="panel">
          <h3>{t("事件回顾", "Event review")}</h3>
          {data.events?.length ? (
            data.events.map((x) => (
              <Link key={x.id} className="insight-row" href={`/events/${x.id}`}>
                <span>{x.title}</span>
                <span className="text-xs text-muted">
                  {x.article_count} {t("篇", "articles")}
                </span>
              </Link>
            ))
          ) : (
            <p className="text-muted mt-4">
              {t(
                "本期暂无已聚类的公开事件",
                "No published clustered events in this period",
              )}
            </p>
          )}
        </div>
      </div>
      <h3 className="mt-6 mb-4">{t("政策盘点", "Policy review")}</h3>
      {data.policies?.length ? (
        <div className="policy-grid">
          {data.policies.map((x) => (
            <PolicyCard key={x.id} policy={x} />
          ))}
        </div>
      ) : (
        <p className="text-muted">
          {t(
            "本期暂无已发布的政策资料",
            "No published policy evidence in this period",
          )}
        </p>
      )}
    </section>
  );
}
