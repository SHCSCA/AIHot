import { useState } from "react";
import type { AdminApi } from "../api";
import { AdminChannelCards, usePersistedAdminChannel } from "../components/AdminChannelCards";
import { Section, TableWrap } from "../components/Section";
import { useAsyncData } from "../hooks";
import { actorLabel } from "../labels";
import type { FeedbackEvent } from "../types";
import { channelLabel, feedbackLabel, formatDateTime } from "../utils";

export function FeedbackView({ api }: { api: AdminApi }) {
  const [channel, setChannel] = usePersistedAdminChannel("admin-feedback-channel");
  const [filters, setFilters] = useState({ feedbackType: "" });
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const { data: events, reload, error } = useAsyncData(() => api.listFeedbackEvents({ channel, ...filters }), [] as FeedbackEvent[], [
    channel,
    filters.feedbackType
  ]);
  const falsePositiveCount = events.filter((event) => event.feedbackType === "false_positive").length;
  const falseNegativeCount = events.filter((event) => event.feedbackType === "false_negative").length;
  const closedCount = events.filter((event) => ["accepted", "ignored"].includes(event.status ?? "")).length;

  async function updateStatus(event: FeedbackEvent, status: string) {
    if (!event.id) return;
    setProcessingId(event.id);
    setActionError(null);
    setActionSuccess(null);
    try {
      await api.updateFeedbackStatus(event.id, status);
      setActionSuccess(`反馈 ${event.id} 已标记为${feedbackStatusLabel(status)}。`);
      await reload();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "反馈处理失败。");
    } finally {
      setProcessingId(null);
    }
  }

  return (
    <div className="view-stack">
      <AdminChannelCards value={channel} onChange={setChannel} metrics={[{ channel, metrics: { sourceCount: events.length } }]} />
      <Section title="反馈质量闭环" description="误选用于校准精选过宽，漏选用于补齐召回不足；采纳或忽略后进入质量样本闭环。">
        <div className="stats-grid">
          <div className="metric metric-bad"><span>误选反馈</span><strong>{falsePositiveCount}</strong></div>
          <div className="metric metric-warn"><span>漏选反馈</span><strong>{falseNegativeCount}</strong></div>
          <div className="metric metric-good"><span>已闭环</span><strong>{closedCount}</strong></div>
        </div>
      </Section>
      <Section
        title="反馈处理"
        description="只读信息区展示用户说明、关联事件和来源；最右侧处理区只更新反馈状态，不直接改变线上评分、精选状态或日报内容。"
        error={error || actionError}
        action={<div className="inline-actions"><select value={filters.feedbackType} onChange={(event) => setFilters({ ...filters, feedbackType: event.target.value })}><option value="">全部类型</option><option value="general">一般反馈</option><option value="false_positive">误选</option><option value="false_negative">漏选</option><option value="promote">建议提权</option><option value="demote">建议降权</option><option value="category_fix">分类修正</option></select><button onClick={reload}>刷新</button></div>}
      >
        {actionSuccess && <p className="hint">{actionSuccess}</p>}
        <TableWrap>
          <table>
            <thead><tr><th>反馈</th><th>质量信号</th><th>关联对象</th><th>用户说明</th><th>状态</th><th>来源</th><th>处理操作</th></tr></thead>
            <tbody>{events.map((event) => <tr key={event.id}><td><strong>{event.id}</strong><span>{channelLabel(event.channel)} · {formatDateTime(event.createdAt)}</span></td><td><strong>{feedbackLabel(event.feedbackType)}</strong><span>{qualityLoopHint(event.feedbackType)}</span></td><td>事件：{event.clusterId ?? "-"}<span>条目：{event.itemId ?? "-"}</span></td><td>{event.reason}<span>{event.contact ? `联系方式：${event.contact}` : "未留联系方式"}</span></td><td><FeedbackStatusBadge value={event.status ?? "unread"} /></td><td>{actorLabel(event.actor)}</td><td><select value={event.status ?? "unread"} disabled={processingId === event.id} onChange={(change) => updateStatus(event, change.target.value)} aria-label={`处理反馈 ${event.id}`}><option value="unread">未处理</option><option value="read">已读</option><option value="accepted">已采纳</option><option value="ignored">已忽略</option></select>{processingId === event.id && <span>处理中...</span>}</td></tr>)}</tbody>
          </table>
        </TableWrap>
        {!events.length && <p className="hint">当前筛选下暂无反馈。</p>}
      </Section>
    </div>
  );
}

function FeedbackStatusBadge({ value }: { value: string }) {
  return <span className={`status status-${value}`}>{feedbackStatusLabel(value)}</span>;
}

function feedbackStatusLabel(value: string) {
  const labels: Record<string, string> = { unread: "未处理", read: "已读", accepted: "已采纳", ignored: "已忽略" };
  return labels[value] ?? value;
}

function qualityLoopHint(value: string) {
  const labels: Record<string, string> = {
    false_positive: "精选过宽，回看排序与拒绝阈值",
    false_negative: "召回不足，回看信源覆盖与筛选阈值",
    promote: "用户认为应提权",
    demote: "用户认为应降权",
    category_fix: "分类质量修正样本",
    general: "通用质量信号"
  };
  return labels[value] ?? "质量信号";
}
