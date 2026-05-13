import { Check, MessageSquare, X } from "lucide-react";
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
  const [note, setNote] = useState("");
  const { data: events, reload, error } = useAsyncData(() => api.listEvents({ reviewStatus }), [] as EventCluster[]);

  async function open(event: EventCluster) {
    setSelected(event);
    const detail = await api.getEventDetail(event.id);
    setMembers(detail.members);
  }

  async function review(event: EventCluster, status: "approved" | "rejected") {
    await api.reviewEvent(event.id, { reviewStatus: status, reviewNote: note, actor: "operator" });
    setNote("");
    reload();
  }

  async function feedback(event: EventCluster) {
    await api.createFeedback({ channel: event.channel, clusterId: event.id, feedbackType: "false_positive", reason: note, actor: "operator" });
    setNote("");
  }

  return (
    <div className="view-stack split-layout">
      <Section title="事件审核" error={error} action={<select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value)}><option value="pending">待审核</option><option value="approved">已通过</option><option value="rejected">已拒绝</option></select>}>
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
              <div className="inline-actions">
                <button className="primary" onClick={() => review(event, "approved")}><Check size={15} />通过</button>
                <button className="danger ghost" onClick={() => review(event, "rejected")}><X size={15} />拒绝</button>
              </div>
            </article>
          ))}
        </div>
      </Section>
      <Section title="事件详情" description={selected ? `${reviewLabel(selected.reviewStatus ?? "pending")} · ${selected.title}` : "选择左侧事件查看成员来源。"}>
        {selected ? (
          <>
            <textarea placeholder="审核备注或反馈原因" value={note} onChange={(event) => setNote(event.target.value)} />
            <div className="inline-actions">
              <button className="primary" onClick={() => review(selected, "approved")}>通过</button>
              <button className="danger ghost" onClick={() => review(selected, "rejected")}>拒绝</button>
              <button className="ghost" onClick={() => feedback(selected)}><MessageSquare size={15} />提交反馈</button>
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
