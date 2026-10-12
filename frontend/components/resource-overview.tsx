"use client";

import Link from "next/link";
import { ArrowUpRight, Gem, Layers3, Sparkles } from "lucide-react";
import { usePreferences } from "@/hooks/use-preferences";
import type { Facets, Price } from "@/types";
import { MineralCrystal } from "./mineral-crystal";

const ELEMENTS: Record<string, [string, string]> = {
  锂: ["Li", "03"],
  铜: ["Cu", "29"],
  金: ["Au", "79"],
  银: ["Ag", "47"],
  锌: ["Zn", "30"],
  镍: ["Ni", "28"],
  钴: ["Co", "27"],
  铀: ["U", "92"],
  铁: ["Fe", "26"],
  铁矿石: ["Fe", "26"],
  石墨: ["C", "06"],
  稀土: ["REE", ""],
};

/** Plot the observed dates at their actual spacing; never interpolate missing quotes. */
function PriceSnapshotChart({
  prices,
  label,
}: {
  prices: Price[];
  label: string;
}) {
  const observations = [...prices]
    .filter(
      (item) =>
        Number.isFinite(Number(item.price)) &&
        Number.isFinite(Date.parse(item.date)),
    )
    .sort((a, b) => a.date.localeCompare(b.date));
  if (!observations.length) return null;
  const values = observations.map((item) => Number(item.price));
  const min = Math.min(...values),
    max = Math.max(...values);
  const first = Date.parse(observations[0].date),
    last = Date.parse(observations[observations.length - 1].date);
  const points = observations.map((item) => ({
    x:
      first === last
        ? 175
        : 8 + ((Date.parse(item.date) - first) / (last - first)) * 334,
    y: min === max ? 40 : 70 - ((Number(item.price) - min) / (max - min)) * 58,
    item,
  }));
  const line = points
    .map(({ x, y }) => `${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");
  return (
    <svg
      viewBox="0 0 350 88"
      className="price-snapshot-chart"
      role="img"
      aria-label={label}
    >
      <title>{label}</title>
      <defs>
        <linearGradient id="price-snapshot-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.22" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[20, 45, 70].map((y) => (
        <line
          key={y}
          x1="0"
          y1={y}
          x2="350"
          y2={y}
          className="snapshot-gridline"
        />
      ))}
      {points.length > 1 && (
        <polygon
          points={`${points[0].x},88 ${line} ${points[points.length - 1].x},88`}
          fill="url(#price-snapshot-fill)"
        />
      )}
      <polyline
        points={line}
        pathLength={1}
        className="snapshot-line"
        fill="none"
        stroke="var(--accent)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      {points.map(({ x, y, item }, index) => (
        <circle
          key={item.id}
          cx={x}
          cy={y}
          r={index === points.length - 1 ? 3.5 : 2}
          fill="var(--accent)"
        >
          <title>{`${item.date} · ${item.price} ${item.currency}/${item.unit}`}</title>
        </circle>
      ))}
    </svg>
  );
}

export function ResourceOverview({
  prices,
  facets,
  pricePending,
  priceError,
}: {
  prices?: Price[];
  facets?: Facets;
  pricePending: boolean;
  priceError: boolean;
}) {
  const { t } = usePreferences();
  const ordered = [...(prices ?? [])].sort((a, b) =>
    b.date.localeCompare(a.date),
  );
  const latest = ordered[0];
  const series = latest
    ? ordered
        .filter(
          (item) =>
            item.product === latest.product &&
            item.currency === latest.currency &&
            item.unit === latest.unit &&
            item.source === latest.source &&
            item.price_type === latest.price_type,
        )
        .slice(0, 30)
    : [];
  const change = latest?.change_pct == null ? null : Number(latest.change_pct);
  const watched = facets?.minerals.slice(0, 5) ?? [];
  return (
    <section
      className="resource-overview"
      aria-label={t("资源观察", "Resource observatory")}
    >
      <article className="observatory-card price-snapshot">
        <div className="observatory-card-heading">
          <span>
            <Gem size={14} />
            {t("价格观察", "Market snapshot")}
          </span>
          <span className="micro-label">PRICE WATCH</span>
        </div>
        <div className="snapshot-product">
          <Link href="/minerals/%E9%94%82" prefetch={false}>
            {t("碳酸锂 · 现货", "Lithium carbonate · Spot")}
            <ArrowUpRight size={13} />
          </Link>
          <span>{t("最新收录报价", "Latest recorded quote")}</span>
        </div>
        {latest ? (
          <>
            <div className="snapshot-value">
              <strong>
                {Number(latest.price).toLocaleString("en-US", {
                  maximumFractionDigits: 2,
                })}
              </strong>
              <span>
                {latest.currency} / {latest.unit}
              </span>
              {change !== null && Number.isFinite(change) && (
                <span
                  className={`snapshot-change ${change > 0 ? "up" : change < 0 ? "down" : "text-muted"}`}
                >
                  {change > 0 ? "+" : ""}
                  {change.toFixed(2)}%
                </span>
              )}
            </div>
            <PriceSnapshotChart
              prices={series}
              label={t(
                "已收录碳酸锂现货价格观测，按实际报价日期绘制",
                "Recorded lithium carbonate spot observations, plotted by quote date",
              )}
            />
            <div className="snapshot-dates">
              <span>{series[series.length - 1]?.date}</span>
              <time dateTime={latest.date}>{latest.date}</time>
            </div>
            <div className="snapshot-source">
              <a
                href={latest.source_url || latest.source}
                target="_blank"
                rel="noopener noreferrer"
              >
                {t("生意社 · 查看报价原文", "SunSirs · Original quotation")}
                <ArrowUpRight size={11} />
              </a>
              <span>{t("涨跌比较上次报价", "Change vs. previous quote")}</span>
            </div>
          </>
        ) : (
          <p className="snapshot-empty">
            {pricePending
              ? t("正在读取价格数据…", "Loading market data…")
              : priceError
                ? t(
                    "价格数据暂时不可用",
                    "Market data is temporarily unavailable",
                  )
                : t("暂无已收录现货报价", "No recorded spot quotations")}
          </p>
        )}
      </article>
      <article className="observatory-card mineral-watch">
        <div className="observatory-card-heading">
          <span>
            <Layers3 size={14} />
            {t("矿种观察", "Commodity watch")}
          </span>
          <Link href="/minerals" prefetch={false} className="micro-link">
            {t("全部矿种", "All minerals")}
            <ArrowUpRight size={12} />
          </Link>
        </div>
        <p className="observatory-card-description">
          {t(
            "从关键矿产到贵金属，按矿种追踪已发布情报。",
            "From critical minerals to precious metals. Follow the published evidence.",
          )}
        </p>
        <div className="element-watchlist">
          {watched.map((item) => (
            <Link
              href={`/minerals/${encodeURIComponent(item.name)}`}
              key={item.name}
              prefetch={false}
              className="element-tile"
            >
              <span className="element-number">
                {ELEMENTS[item.name]?.[1] || "MIN"}
              </span>
              <strong>{ELEMENTS[item.name]?.[0] || "◈"}</strong>
              <span className="element-name">{item.name}</span>
              <span className="element-count">
                {item.count} {t("篇", "stories")}
              </span>
            </Link>
          ))}
        </div>
        {!watched.length && (
          <p className="subtitle">
            {t(
              "矿种目录正在等待已发布资料",
              "Waiting for published commodity coverage",
            )}
          </p>
        )}
        <div className="mineral-watch-foot">
          <span className="atlas-legend-dot" />
          {t(
            "文章数来自当前已发布资料库",
            "Counts reflect the published article archive",
          )}
        </div>
      </article>
      <article className="observatory-card research-entry">
        <MineralCrystal />
        <div className="observatory-card-heading">
          <span>
            <Sparkles size={14} />
            矿眸智探
          </span>
          <span className="micro-label">ASK INTELLIGENCE</span>
        </div>
        <h2>
          {t("变化背后，", "Beyond the headlines.")}
          <br />
          <span>{t("找到你的答案。", "Find your answer.")}</span>
        </h2>
        <p>
          {t(
            "串联市场与政策，从原始资料中寻找线索。回答附来源，判断有依据。",
            "Connect market and policy signals. Ask a question and follow the sources behind the answer.",
          )}
        </p>
        <Link
          href={`/chat?q=${encodeURIComponent(t("锂价最近有哪些变化？", "What changed in lithium prices?"))}`}
          prefetch={false}
          className="research-question"
        >
          <span>
            {t("锂价最近有哪些变化？", "What changed in lithium prices?")}
          </span>
          <ArrowUpRight size={15} />
        </Link>
      </article>
    </section>
  );
}
