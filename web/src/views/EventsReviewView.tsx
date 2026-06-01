import { useState } from "react";
import type { AdminApi } from "../api";
import { AdminChannelCards, usePersistedAdminChannel } from "../components/AdminChannelCards";
import { Section, TableWrap } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { useAsyncData } from "../hooks";
import { actorLabel, categoryLabel, screenBucketLabel, screenReasonCodeLabel } from "../labels";
import type { EventCluster, EventMember } from "../types";
import { channelLabel, formatDateTime, reviewLabel } from "../utils";

export function EventsReviewView({ api }: { api: AdminApi }) {
  const [channel, setChannel] = usePersistedAdminChannel("admin-events-channel");
  const [reviewStatus, setReviewStatus] = useState("pending");
  const [selected, setSelected] = useState<EventCluster | null>(null);
  const [members, setMembers] = useState<EventMember[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [reviewNote, setReviewNote] = useState("");
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [reviewSuccess, setReviewSuccess] = useState<string | null>(null);
  const { data: events, reload, error } = useAsyncData(() => api.listEvents({ channel, reviewStatus }), [] as EventCluster[], [
    channel,
    reviewStatus
  ]);

  async function open(event: EventCluster) {
    setSelected(event);
    setMembers([]);
    setDetailError(null);
    setReviewError(null);
    setReviewSuccess(null);
    setReviewNote(event.reviewNote ?? "");
    setDetailLoading(true);
    try {
      const detail = await api.getEventDetail(event.id);
      setSelected(detail.event);
      setMembers(detail.members);
      setReviewNote(detail.event.reviewNote ?? "");
    } catch (error) {
      setDetailError(error instanceof Error ? error.message : "事件详情加载失败。");
    } finally {
      setDetailLoading(false);
    }
  }

  async function submitReview(reviewStatus: "approved" | "rejected" | "pending") {
    if (!selected) return;
    setReviewing(reviewStatus);
    setReviewError(null);
    setReviewSuccess(null);
    try {
      const updated = await api.reviewEvent(selected.id, {
        reviewStatus,
        reviewNote: reviewNote.trim() || null,
        actor: "operator"
      });
      setSelected(updated);
      setReviewNote(updated.reviewNote ?? "");
      setReviewSuccess(`审核状态已更新为${reviewLabel(updated.reviewStatus ?? reviewStatus)}。`);
      await reload();
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "审核操作失败。");
    } finally {
      setReviewing(null);
    }
  }

  return (
    <div className="view-stack split-layout">
      <div className="view-stack">
        <AdminChannelCards value={channel} onChange={setChannel} metrics={[{ channel, metrics: { sourceCount: events.length } }]} />
        <Section title="事件审核队列" description="左侧按审核状态列出事件簇，右侧展示簇结构、成员来源、系统结论和可执行审核操作。" error={error} action={<div className="inline-actions"><select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value)}><option value="pending">待系统确认</option><option value="approved">已通过</option><option value="rejected">已拒绝</option></select><button onClick={reload}>刷新</button></div>}>
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
                  <span>{event.memberCount} 条成员</span>
                  <span>{formatDateTime(event.lastSeenAt)}</span>
                  <StatusLabel value={event.reviewStatus ?? "pending"} />
                </div>
              </article>
            ))}
            {!events.length && <p className="hint">当前筛选下暂无事件。</p>}
          </div>
        </Section>
      </div>
      <Section title="事件详情" description={selected ? `${reviewLabel(selected.reviewStatus ?? "pending")} · ${selected.title}` : "选择左侧事件查看成员来源。"}>
        {selected ? (
          <>
            <div className="readonly-panel">
              <h3>事件簇</h3>
              <div className="event-meta">
                <span>{channelLabel(selected.channel)}</span>
                <span>{categoryLabel(selected.category)}</span>
                <span>精选分 {Math.round(selected.score)}</span>
                <span>{selected.sourceCount} 个来源</span>
                <span>{selected.memberCount} 条成员</span>
              </div>
              <p>{selected.mainItem?.summary ?? "暂无摘要。"}</p>
              <p className="hint">首次发现：{formatDateTime(selected.firstSeenAt)} · 最近更新：{formatDateTime(selected.lastSeenAt)}</p>
            </div>
            <div className="readonly-panel review-note">
              <h3>系统结论</h3>
              <div className="event-meta">
                <StatusLabel value={selected.reviewStatus ?? "pending"} />
                <span>{screenBucketLabel(selected.screenBucket)}</span>
                <span>{screenReasonCodeLabel(selected.screenReasonCode)}</span>
              </div>
              <strong>{selected.reviewNote || selected.screenReason || "暂无系统备注。"}</strong>
              <span>复核人：{actorLabel(selected.reviewedBy)} · 复核时间：{formatDateTime(selected.reviewedAt)}</span>
              {selected.riskFlags?.length ? <span>风险标记：{selected.riskFlags.join("、")}</span> : <span>风险标记：无</span>}
            </div>
            {detailLoading && <p className="hint">正在加载成员来源...</p>}
            {detailError && <p className="error">{detailError}</p>}
            <TableWrap>
              <table>
                <thead><tr><th>成员来源</th><th>来源属性</th><th>关联分</th><th>主条目</th></tr></thead>
                <tbody>{members.map((member) => <tr key={member.id}><td><strong>{member.title}</strong><span>{member.summary ?? "暂无摘要"}</span></td><td>{member.sourceName ?? "-"}<span>{member.sourceGroup ?? member.sourceType ?? "-"}</span></td><td>{member.relationScore ?? "-"}</td><td>{member.isMain ? "是" : "否"}</td></tr>)}</tbody>
              </table>
            </TableWrap>
            {!detailLoading && !members.length && <p className="hint">暂无成员来源。</p>}
            <div className="operation-panel">
              <h3>审核操作</h3>
              <label>审核备注<textarea value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} placeholder="记录通过、拒绝或退回待处理的原因。" /></label>
              <div className="inline-actions">
                <button className="primary" onClick={() => submitReview("approved")} disabled={Boolean(reviewing)}>{reviewing === "approved" ? "提交中..." : "通过"}</button>
                <button className="danger" onClick={() => submitReview("rejected")} disabled={Boolean(reviewing)}>{reviewing === "rejected" ? "提交中..." : "拒绝"}</button>
                <button className="ghost" onClick={() => submitReview("pending")} disabled={Boolean(reviewing)}>{reviewing === "pending" ? "提交中..." : "退回待处理"}</button>
              </div>
              {reviewError && <p className="error">{reviewError}</p>}
              {reviewSuccess && <p className="hint">{reviewSuccess}</p>}
            </div>
          </>
        ) : <p className="hint">暂无选中事件。</p>}
      </Section>
    </div>
  );
}
