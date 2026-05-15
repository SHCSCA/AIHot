import { useState } from "react";
import type { AdminApi } from "../api";
import { AdminChannelCards, usePersistedAdminChannel } from "../components/AdminChannelCards";
import { Section, TableWrap } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { useAsyncData } from "../hooks";
import type { FeedbackEvent } from "../types";
import { channelLabel, feedbackLabel, formatDateTime } from "../utils";

export function FeedbackView({ api }: { api: AdminApi }) {
  const [channel, setChannel] = usePersistedAdminChannel("admin-feedback-channel");
  const [filters, setFilters] = useState({ feedbackType: "" });
  const { data: events, reload, error } = useAsyncData(() => api.listFeedbackEvents({ channel, ...filters }), [] as FeedbackEvent[], [
    channel,
    filters.feedbackType
  ]);

  async function updateStatus(event: FeedbackEvent, status: string) {
    if (!event.id) return;
    await api.updateFeedbackStatus(event.id, status);
    reload();
  }

  return (
    <div className="view-stack">
      <AdminChannelCards value={channel} onChange={setChannel} metrics={[{ channel, metrics: { sourceCount: events.length } }]} />
      <Section
        title="反馈历史"
        description="反馈来自前台用户提交，只作为质量信号和评估样本，不自动改变线上评分、精选状态或日报内容。"
        error={error}
        action={<div className="inline-actions"><select value={filters.feedbackType} onChange={(event) => setFilters({ ...filters, feedbackType: event.target.value })}><option value="">全部类型</option><option value="general">一般反馈</option><option value="false_positive">误选</option><option value="false_negative">漏选</option><option value="promote">建议提权</option><option value="demote">建议降权</option><option value="category_fix">分类修正</option></select><button onClick={reload}>刷新</button></div>}
      >
        <TableWrap>
          <table>
            <thead><tr><th>ID</th><th>频道</th><th>事件</th><th>类型</th><th>用户说明</th><th>联系方式</th><th>状态</th><th>来源</th><th>时间</th><th>处理</th></tr></thead>
            <tbody>{events.map((event) => <tr key={event.id}><td>{event.id}</td><td>{channelLabel(event.channel)}</td><td>{event.clusterId ?? "-"}</td><td>{feedbackLabel(event.feedbackType)}</td><td>{event.reason}</td><td>{event.contact ?? "-"}</td><td><StatusLabel value={event.status ?? "unread"} /></td><td>{event.actor === "public-user" ? "前台用户" : event.actor}</td><td>{formatDateTime(event.createdAt)}</td><td><select value={event.status ?? "unread"} onChange={(change) => updateStatus(event, change.target.value)}><option value="unread">未处理</option><option value="read">已读</option><option value="accepted">已采纳</option><option value="ignored">已忽略</option></select></td></tr>)}</tbody>
          </table>
        </TableWrap>
      </Section>
    </div>
  );
}
