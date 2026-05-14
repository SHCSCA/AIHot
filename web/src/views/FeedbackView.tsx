import { useState } from "react";
import type { AdminApi } from "../api";
import { Section, TableWrap } from "../components/Section";
import { useAsyncData } from "../hooks";
import type { FeedbackEvent } from "../types";
import { channelLabel, feedbackLabel, formatDateTime } from "../utils";

export function FeedbackView({ api }: { api: AdminApi }) {
  const [filters, setFilters] = useState({ channel: "ai", feedbackType: "" });
  const { data: events, reload, error } = useAsyncData(() => api.listFeedbackEvents(filters), [] as FeedbackEvent[]);
  return (
    <div className="view-stack">
      <Section
        title="反馈历史"
        description="反馈来自前台用户提交，只作为质量信号和评估样本，不自动改变线上评分、精选状态或日报内容。"
        error={error}
        action={<div className="inline-actions"><select value={filters.channel} onChange={(event) => setFilters({ ...filters, channel: event.target.value })}><option value="ai">AI 热点</option><option value="amazon">Amazon 情报</option></select><select value={filters.feedbackType} onChange={(event) => setFilters({ ...filters, feedbackType: event.target.value })}><option value="">全部类型</option><option value="false_positive">误选</option><option value="false_negative">漏选</option><option value="promote">建议提权</option><option value="demote">建议降权</option><option value="category_fix">分类修正</option></select><button onClick={reload}>刷新</button></div>}
      >
        <TableWrap>
          <table>
            <thead><tr><th>ID</th><th>频道</th><th>事件</th><th>类型</th><th>用户说明</th><th>来源</th><th>时间</th></tr></thead>
            <tbody>{events.map((event) => <tr key={event.id}><td>{event.id}</td><td>{channelLabel(event.channel)}</td><td>{event.clusterId ?? "-"}</td><td>{feedbackLabel(event.feedbackType)}</td><td>{event.reason}</td><td>{event.actor === "public-user" ? "前台用户" : event.actor}</td><td>{formatDateTime(event.createdAt)}</td></tr>)}</tbody>
          </table>
        </TableWrap>
      </Section>
    </div>
  );
}
