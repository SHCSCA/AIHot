import type { ReactNode } from "react";

export function MetricCard({
  label,
  value,
  tone = "neutral",
  detail
}: {
  label: string;
  value: ReactNode;
  tone?: string;
  detail?: ReactNode;
}) {
  const classes = ["metric", "metric-token", `metric-${tone}`].join(" ");

  return (
    <div className={classes} data-tone={tone} aria-label={`${label}: ${String(value)}`}>
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
      {detail && <em className="metric-detail">{detail}</em>}
    </div>
  );
}

export function MetricGrid({ children }: { children: ReactNode }) {
  return <div className="stats-grid">{children}</div>;
}
