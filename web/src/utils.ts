import { channelLabel as resolvedChannelLabel, feedbackTypeLabel, fetchAdapterLabel } from "./labels";

export function channelLabel(value: string) {
  return resolvedChannelLabel(value);
}

export function adapterLabel(value: string) {
  return fetchAdapterLabel(value);
}

export function visibilityLabel(value: string) {
  const labels: Record<string, string> = { public: "公开", internal: "内部", hidden: "隐藏" };
  return labels[value] ?? value;
}

export function reviewLabel(value: string) {
  const labels: Record<string, string> = { pending: "待审核", approved: "已通过", rejected: "已拒绝" };
  return labels[value] ?? value;
}

export function feedbackLabel(value: string) {
  return feedbackTypeLabel(value);
}

export function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function formatDateTime(value?: string | null) {
  if (!value) return "未设置";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

export function formatMonthDay(value?: string | null) {
  if (!value) return "未设置";
  return new Date(value).toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
}

export function formatTime(value?: string | null) {
  if (!value) return "--:--";
  return new Date(value).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
}

export function jsonLabel(value: unknown): string {
  if (!value || (typeof value === "object" && Object.keys(value).length === 0)) return "未配置";
  if (Array.isArray(value)) return value.map(jsonLabel).join("；");
  if (typeof value === "object") {
    return Object.entries(value)
      .map(([key, entry]) => `${configKeyLabel(key)}：${jsonValueLabel(entry)}`)
      .join("；");
  }
  return jsonValueLabel(value);
}

export function today() {
  return new Date().toISOString().slice(0, 10);
}

function configKeyLabel(value: string) {
  const labels: Record<string, string> = {
    selected: "精选阈值",
    provider: "模型供应商",
    model: "模型",
    highlights: "重点事件",
    selectedEventCount: "精选事件数",
    feedbackCount: "反馈总数",
    falsePositiveCount: "误选反馈",
    falseNegativeCount: "漏选反馈",
    categoryDistribution: "分类分布",
    sourceContribution: "来源贡献"
  };
  return labels[value] ?? value;
}

function jsonValueLabel(value: unknown): string {
  if (value === null || value === undefined || value === "") return "未设置";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) return `${value.length} 项`;
  if (typeof value === "object") return Object.entries(value).map(([key, entry]) => `${configKeyLabel(key)} ${entry}`).join("，");
  return String(value);
}
