import { Bot, ShoppingBag } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { channelLabel } from "../utils";

export type AdminChannel = "ai" | "amazon";

type ChannelMetric = {
  channel: string;
  metrics?: Record<string, number | undefined>;
};

type AdminChannelCardsProps = {
  value: AdminChannel;
  onChange: (channel: AdminChannel) => void;
  metrics?: ChannelMetric[];
};

const channels: Array<{ id: AdminChannel; description: string; Icon: typeof Bot }> = [
  { id: "ai", description: "模型、产品、Agent、论文和行业变化", Icon: Bot },
  { id: "amazon", description: "政策、账号、物流、广告和选品情报", Icon: ShoppingBag }
];

export function usePersistedAdminChannel(key: string, initial: AdminChannel = "ai") {
  const [channel, setChannel] = useState<AdminChannel>(() => {
    const stored = localStorage.getItem(key);
    return stored === "amazon" || stored === "ai" ? stored : initial;
  });

  useEffect(() => {
    localStorage.setItem(key, channel);
  }, [channel, key]);

  return [channel, setChannel] as const;
}

export function AdminChannelCards({ value, onChange, metrics = [] }: AdminChannelCardsProps) {
  const metricMap = useMemo(() => new Map(metrics.map((item) => [item.channel, item.metrics ?? {}])), [metrics]);
  return (
    <div className="admin-channel-cards" role="group" aria-label="频道切换">
      {channels.map(({ id, description, Icon }) => {
        const channelMetrics = metricMap.get(id) ?? {};
        const summary = channelSummary(channelMetrics);
        return (
          <button
            key={id}
            type="button"
            aria-selected={value === id}
            aria-pressed={value === id}
            className={value === id ? "admin-channel-card active" : "admin-channel-card"}
            onClick={() => onChange(id)}
          >
            <span className="admin-channel-icon"><Icon size={18} /></span>
            <span>
              <strong>{channelLabel(id)}</strong>
              <em>{description}</em>
            </span>
            <small>{summary}</small>
          </button>
        );
      })}
    </div>
  );
}

function channelSummary(metrics: Record<string, number | undefined>) {
  const sourceCount = Number(metrics.sourceCount ?? 0);
  const warnings = Number(metrics.healthWarningCount ?? 0);
  const failedJobs = Number(metrics.failedJobCount ?? 0);
  const pendingReviews = Number(metrics.pendingReviewEventCount ?? 0);
  const riskParts = [
    warnings > 0 ? `${warnings} 告警` : null,
    failedJobs > 0 ? `${failedJobs} 失败` : null,
    pendingReviews > 0 ? `${pendingReviews} 待审` : null
  ].filter(Boolean);

  return riskParts.length ? `${sourceCount} 信源 · ${riskParts.join(" · ")}` : `${sourceCount} 信源 · 运行正常`;
}
