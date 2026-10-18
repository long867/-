"use client";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { usePageMotion } from "@/hooks/use-page-motion";
export default function DigestChart({
  minerals,
}: {
  minerals: Record<string, number>;
}) {
  const { enabled } = usePageMotion();
  const data = Object.entries(minerals)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name, count]) => ({ name, count }));
  return (
    <div
      className="h-60"
      role="img"
      aria-label={data.map((x) => `${x.name}: ${x.count}`).join("; ")}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 10, right: 10, bottom: 0, left: -20 }}
        >
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fill: "var(--muted)", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 10,
              color: "var(--text)",
            }}
          />
          <Bar
            dataKey="count"
            name="报道 / Articles"
            fill="var(--accent)"
            radius={[4, 4, 0, 0]}
            maxBarSize={40}
            isAnimationActive={enabled}
            animationDuration={900}
            animationEasing="ease-out"
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
