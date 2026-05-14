import { useState } from "react";
import type { AdminApi } from "../api";
import { Section, TableWrap } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { useAsyncData } from "../hooks";
import { categoryLabel } from "../labels";
import type { EventCluster, EventMember } from "../types";
import { channelLabel, formatDateTime, reviewLabel } from "../utils";

export function EventsReviewView({ api }: { api: AdminApi }) {
  const [reviewStatus, setReviewStatus] = useState("pending");
  const [selected, setSelected] = useState<EventCluster | null>(null);
  const [members, setMembers] = useState<EventMember[]>([]);
  const { data: events, reload, error } = useAsyncData(() => api.listEvents({ reviewStatus }), [] as EventCluster[]);

  async function open(event: EventCluster) {
    setSelected(event);
    const detail = await api.getEventDetail(event.id);
    setMembers(detail.members);
  }

  return (
    <div className="view-stack split-layout">
      <Section title="AI 自动评审监控" description="事件审核由初筛、精筛和 RankPolicy 自动完成；这里用于查看状态、原因和来源，不做人工放行。" error={error} action={<div className="inline-actions"><select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value)}><option value="pending">待系统确认</option><option value="approved">已自动通过</option><option value="rejected">已自动拒绝</option></select><button onClick={reload}>刷新</button></div>}>
        <div className="admin-review-list">
          {events.map((event) => (
            <article key={event.id} className={selected?.id === event.id ? "admin-review-item active" : "admin-review-item"}>
              <button className="link-button" onClick={() => open(event)}>{event.title}</button>
              <p>{event.mainItem?.summary ?? "暂无摘要。"}</p>
              <div className="event-meta">
                <span>{channelLabel(event.channel)}</span>
                <span>{categoryLabel(event.category)}</span>
                <span>精选分 {Math.round(event.score)}</span>
                <span>{event.sourceCount} 个来源</span>
                <span>{formatDateTime(event.lastSeenAt)}</span>
                <StatusLabel value={event.reviewStatus ?? "pending"} />
              </div>
            </article>
          ))}
        </div>
      </Section>
      <Section title="事件详情" description={selected ? `${reviewLabel(selected.reviewStatus ?? "pending")} · ${selected.title}` : "选择左侧事件查看成员来源。"}>
        {selected ? (
          <>
            <div className="review-note">
              <strong>系统结论</strong>
              <span>{selected.reviewNote || selected.screenReason || "暂无系统备注。"}</span>
            </div>
            <TableWrap>
              <table>
                <thead><tr><th>成员</th><th>来源</th><th>主条目</th></tr></thead>
                <tbody>{members.map((member) => <tr key={member.id}><td>{member.title}</td><td>{member.sourceName}</td><td>{member.isMain ? "是" : "否"}</td></tr>)}</tbody>
              </table>
            </TableWrap>
          </>
        ) : <p className="hint">暂无选中事件。</p>}
      </Section>
    </div>
  );
}
