"use client";
import {
  BarChart,
  Bar,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { usePreferences } from "@/hooks/use-preferences";
import { usePageMotion } from "@/hooks/use-page-motion";
export default function ReportChart({
  data,
}: {
  data: { date: string; count: number }[];
}) {
  const { t } = usePreferences();
  const { enabled } = usePageMotion();
  return (
    <div
      className="h-60"
      role="img"
      aria-label={t(
        "统计周期每日已发布报道数量",
        "Daily published coverage in this report period",
      )}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={(x) => String(x).slice(5)}
            tick={{ fontSize: 10, fill: "var(--muted)" }}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 10, fill: "var(--muted)" }}
          />
          <Tooltip
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
            }}
          />
          <Bar
            dataKey="count"
            name={t("报道数", "Articles")}
            fill="var(--accent)"
            isAnimationActive={enabled}
            animationDuration={900}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
