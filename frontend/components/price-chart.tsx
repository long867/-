"use client";
import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import { usePreferences } from "@/hooks/use-preferences";
import type { Price } from "@/types";
export function PriceChart({ prices }: { prices: Price[] }) {
  const { t } = usePreferences();
  const groups = new Map<string, Price[]>();
  for (const price of prices) {
    const key = [
      price.source,
      price.currency,
      price.unit,
      price.product || price.mineral,
      price.price_type,
    ].join("|");
    groups.set(key, [...(groups.get(key) || []), price]);
  }
  const [selected, setSelected] = useState("");
  const series =
    groups.get(selected) ||
    (groups.values().next().value as Price[] | undefined);
  const sorted = [...(series || [])].sort((a, b) =>
    a.date.localeCompare(b.date),
  );
  if (!sorted.length)
    return (
      <div className="empty">
        {t(
          "暂无该矿种的公开价格记录。",
          "No public price series available for this commodity.",
        )}
      </div>
    );
  const last = sorted[sorted.length - 1];
  const unit = `${last.currency}/${last.unit}`;
  const data = sorted.map((item) => ({
    date: item.date,
    price: Number(item.price),
  }));
  return (
    <section className="panel" aria-label={t("价格走势图", "Price chart")}>
      <div className="flex justify-between items-start gap-4">
        <div>
          <div className="eyebrow">{t("价格观察", "PRICE OBSERVATORY")}</div>
          <h2 className="mt-3">{last.product || last.mineral}</h2>
        </div>
        <span className="chip">
          {last.price_type === "futures"
            ? t("期货", "Futures")
            : t("现货", "Spot")}
        </span>
      </div>
      {groups.size > 1 && (
        <select
          className="w-full mt-4"
          aria-label={t("价格序列", "Price series")}
          value={selected || groups.keys().next().value}
          onChange={(e) => setSelected(e.target.value)}
        >
          {Array.from(groups).map(([key, items]) => (
            <option key={key} value={key}>
              {items[0].product || items[0].mineral} · {items[0].currency}/
              {items[0].unit} ·{" "}
              {items[0].source.replace(/^https?:\/\//, "").split("/")[0]}
            </option>
          ))}
        </select>
      )}
      <div className="flex items-end gap-5 mt-5">
        <div className="price-value">
          {Number(last.price).toLocaleString()}
          <small>{unit}</small>
        </div>
        {last.change_pct !== null && (
          <span className={Number(last.change_pct) > 0 ? "up" : "down"}>
            {Number(last.change_pct) > 0 ? "+" : ""}
            {Number(last.change_pct).toFixed(2)}%
          </span>
        )}
      </div>
      <p className="text-[10px] text-muted mt-2">
        {t("最新记录", "Latest observation")} {last.date} ·{" "}
        {t(
          "与前一观测比较，非日内实时报价",
          "Compared with the preceding observation; not a live quote",
        )}
      </p>
      <div className="chart-frame">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 10, right: 12, left: 0, bottom: 8 }}
          >
            <CartesianGrid
              stroke="var(--border)"
              strokeDasharray="3 5"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: "var(--muted)" }}
              tickFormatter={(value) => value.slice(5)}
              axisLine={false}
              tickLine={false}
              minTickGap={20}
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fontSize: 10, fill: "var(--muted)" }}
              tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
              axisLine={false}
              tickLine={false}
              width={48}
            />
            <Tooltip
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                color: "var(--text)",
                fontSize: 11,
              }}
              formatter={(value: number) => [
                `${value.toLocaleString()} ${unit}`,
                t("价格", "Price"),
              ]}
            />
            <Line
              type="linear"
              dataKey="price"
              stroke="var(--accent)"
              strokeWidth={2}
              dot={{ r: 3, strokeWidth: 2, fill: "var(--surface)" }}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="flex justify-between gap-3 text-[10px] text-muted mt-4">
        <span>
          {sorted[0].date} — {last.date} · {sorted.length}{" "}
          {t("个观测", "observations")}
        </span>
        <a
          className="source-link"
          href={last.source_url || last.source}
          target="_blank"
          rel="noopener noreferrer"
        >
          {t("核对原始数据", "Verify original data")} ↗
        </a>
      </div>
    </section>
  );
}
