import { useState } from "react";
import type { AdminApi } from "../api";
import { Section, TableWrap } from "../components/Section";
import { useAsyncData } from "../hooks";
import type { FeedbackEvent } from "../types";
import { channelLabel, feedbackLabel, formatDateTime } from "../utils";

export function FeedbackView({ api }: { api: AdminApi }) {
  const [filters, setFilters] = useState({ channel: "ai", feedbackType: "" });
  const [form, setForm] = useState({ channel: "ai", feedbackType: "false_positive", reason: "", actor: "operator", clusterId: "" });
  const { data: events, reload, error } = useAsyncData(() => api.listFeedbackEvents(filters), [] as FeedbackEvent[]);
  async function submit() {
    await api.createFeedback({ ...form, clusterId: form.clusterId || null });
    setForm({ ...form, reason: "" });
    reload();
  }
  return (
    <div className="view-stack split-layout">
      <Section title="提交人工反馈" description="反馈进入策略评估统计，不直接覆盖历史评分。">
        <div className="form-grid">
          <label>频道<select value={form.channel} onChange={(event) => setForm({ ...form, channel: event.target.value })}><option value="ai">AI 热点</option><option value="amazon">Amazon 情报</option></select></label>
          <label>反馈类型<select value={form.feedbackType} onChange={(event) => setForm({ ...form, feedbackType: event.target.value })}><option value="false_positive">误选</option><option value="false_negative">漏选</option><option value="promote">提权</option><option value="demote">降权</option><option value="category_fix">分类修正</option></select></label>
          <label>事件 ID<input value={form.clusterId} onChange={(event) => setForm({ ...form, clusterId: event.target.value })} /></label>
          <label>操作人<input value={form.actor} onChange={(event) => setForm({ ...form, actor: event.target.value })} /></label>
        </div>
        <label>原因<textarea value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} /></label>
        <button className="primary" onClick={submit}>提交反馈</button>
      </Section>
      <Section title="反馈历史" error={error} action={<select value={filters.feedbackType} onChange={(event) => setFilters({ ...filters, feedbackType: event.target.value })}><option value="">全部类型</option><option value="false_positive">误选</option><option value="false_negative">漏选</option><option value="promote">提权</option><option value="demote">降权</option></select>}>
        <TableWrap>
          <table>
            <thead><tr><th>ID</th><th>频道</th><th>事件</th><th>类型</th><th>原因</th><th>操作人</th><th>时间</th></tr></thead>
            <tbody>{events.map((event) => <tr key={event.id}><td>{event.id}</td><td>{channelLabel(event.channel)}</td><td>{event.clusterId ?? "-"}</td><td>{feedbackLabel(event.feedbackType)}</td><td>{event.reason}</td><td>{event.actor}</td><td>{formatDateTime(event.createdAt)}</td></tr>)}</tbody>
          </table>
        </TableWrap>
      </Section>
    </div>
  );
}
