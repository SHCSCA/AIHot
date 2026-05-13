import type { ReactNode } from "react";

export function MetricCard({ label, value, tone = "neutral" }: { label: string; value: ReactNode; tone?: string }) {
  return (
    <div className={`metric metric-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function MetricGrid({ children }: { children: ReactNode }) {
  return <div className="stats-grid">{children}</div>;
}
