/** Small real-observation series without a chart library on the critical path. */
export function Sparkline({
  values,
  label,
}: {
  values: number[];
  label: string;
}) {
  const max = Math.max(1, ...values);
  const points = values
    .map(
      (value, i) =>
        `${4 + (i * 112) / Math.max(1, values.length - 1)},${36 - (value / max) * 30}`,
    )
    .join(" ");
  return (
    <svg
      viewBox="0 0 120 42"
      className="sparkline"
      role="img"
      aria-label={label}
    >
      <title>{label}</title>
      <line x1="4" y1="36" x2="116" y2="36" stroke="var(--border)" />
      <polyline
        points={points}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      {values.map((value, i) => (
        <circle
          key={i}
          cx={4 + (i * 112) / Math.max(1, values.length - 1)}
          cy={36 - (value / max) * 30}
          r="2"
          fill="var(--accent)"
        />
      ))}
    </svg>
  );
}
