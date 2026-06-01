import { useState } from "react";
import { motion } from "framer-motion";
import { ExternalLink } from "lucide-react";
import type { PublicApi } from "../../api";
import type { EventMember, MainItem, PublicEvent, PublicEventDetail } from "../../types";
import { useAsyncData } from "../../hooks";
import { formatDateTime, formatMonthDay, formatTime } from "../../utils";
import { categoryLabel, sellerActionLevelLabel, sourceGroupLabel } from "../../labels";

interface EventCardProps {
  event: PublicEvent;
  api?: PublicApi;
  showDate: boolean;
}

export function EventCard({ event, api, showDate }: EventCardProps) {
  const [open, setOpen] = useState(false);
  const { data: detail, reload, loading, error } = useAsyncData<PublicEventDetail | null>(
    () => (open && api ? api.getEventDetail(event.id) : Promise.resolve(null)),
    null,
    [open, event.id, api]
  );

  const summary = event.summary || event.mainItem?.summary || "待 AI 处理后生成中文摘要。";
  const reason = formatReason(event.entryReason || event.suggestedAction || `来自 ${event.sourceCount} 个来源，系统评分达到精选阈值。`);
  const suggestedAction = event.suggestedAction || (event.channel === "amazon" && event.sellerActionLevel
    ? sellerActionLevelLabel(event.sellerActionLevel)
    : "继续跟进主来源和相关来源。");
  const scoreClass = event.score > 85 ? "score-high" : event.score >= 70 ? "score-mid" : "score-low";
  const signalTags = event.channel === "amazon" ? amazonSignalTags(event) : aiSignalTags(event);
  const detailId = `event-detail-${event.id}`;
  const detailEvent = detail?.event ?? event;
  const members = detail?.members ?? [];
  const mainMember = members.find((member) => member.isMain);
  const mainSource = mainMember ?? detailEvent.mainItem ?? event.mainItem;
  const relatedMembers = members.filter((member) => !member.isMain);
  const keyFacts = detailEvent.keyFacts?.filter(Boolean) ?? [];

  function toggleDetail() {
    const nextOpen = !open;
    setOpen(nextOpen);
    if (nextOpen && api) reload();
  }

  return (
    <motion.article
      className="aihot-event"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="timeline-stamp dark">
        {showDate && <span className="timeline-date">{formatMonthDay(event.lastSeenAt)}</span>}
        <strong>{formatTime(event.lastSeenAt)}</strong>
      </div>

      <div className="aihot-event-card glass breathing-card breathing-idle">
        <span className="event-card-breath" aria-hidden="true" />
        <div className="event-meta dark">
          <span>{event.mainItem?.sourceName ?? "未知来源"}</span>
          {event.socialHandle && <span>{event.socialHandle}</span>}
          <span>{sourceGroupLabel(event.sourceGroup)}</span>
          <span>{categoryLabel(event.category)}</span>
          <span>{formatDateTime(event.lastSeenAt)}</span>
        </div>

        <div className="event-title-row">
          <h2>{event.title}</h2>
          <span className={`score-badge ${scoreClass}`} aria-label={`精选分 ${Math.round(event.score)}`}>
            精选分 {Math.round(event.score)}
          </span>
        </div>

        {event.mainItem?.imageUrl && (
          <figure className="event-media event-media-natural">
            <img src={event.mainItem.imageUrl} alt={event.mainItem.imageAlt || event.title} loading="lazy" />
          </figure>
        )}

        <p className="event-summary">{summary}</p>

        <div className="event-stat-strip" aria-label="事件指标">
          <span><small>来源数</small><strong>{event.sourceCount}</strong></span>
          <span><small>成员数</small><strong>{event.memberCount}</strong></span>
          <span><small>精选分</small><strong>{Math.round(event.score)}</strong></span>
        </div>

        {signalTags.length > 0 && (
          <div className="event-tags dark" role="list" aria-label="事件标签">
            {signalTags.map((tag: string) => <span className={tagClass(tag)} key={tag} role="listitem">{tag}</span>)}
          </div>
        )}

        <div className="event-reason-highlight" aria-label="推荐理由和建议动作">
          <div className="event-reason-copy"><small>推荐理由</small><span>{reason}</span></div>
          <div className="event-action-copy"><small>建议动作</small><span>{suggestedAction}</span></div>
          {event.sellerActionLevel && <em>{sellerActionLevelLabel(event.sellerActionLevel)}</em>}
          {event.confidenceScore != null && <em>置信度 {Math.round(event.confidenceScore)}</em>}
        </div>

        <div className="event-foot">
          <span>{event.sourceCount} 个来源</span>
          <span>{event.memberCount} 条相关</span>
          {event.mainItem?.url && (
            <a href={event.mainItem.url} target="_blank" rel="noreferrer">
              <ExternalLink size={15} />查看原文
            </a>
          )}
          <button className="ghost dark" onClick={toggleDetail} aria-expanded={open} aria-controls={detailId}>
            {open ? "收起详情" : "事件详情"}
          </button>
        </div>

        {open && (
          <div id={detailId} className="public-detail dark" role="region" aria-label="事件详情">
            {loading && <p className="hint" aria-live="polite">正在加载详情...</p>}
            {error && <p className="error" role="alert">{error}</p>}
            {!loading && !error && !api && <p className="hint">当前上下文未提供详情 API。</p>}
            {!loading && !error && api && (
              <>
                <div className="event-detail-section event-detail-member-summary" aria-label="成员来源">
                  <h3>成员来源</h3>
                  <div className="event-detail-stats">
                    <span>{members.length || event.memberCount} 个成员</span>
                    <span>{event.sourceCount} 个来源</span>
                    <span>主来源 {mainSource?.sourceName ?? "未知"}</span>
                  </div>
                </div>
                <div className="event-detail-section" aria-label="主来源">
                  <h3>主来源</h3>
                  {mainSource ? (
                    <SourceEvidenceLink item={mainSource} relation="主来源" />
                  ) : (
                    <p className="hint">暂无主来源信息。</p>
                  )}
                </div>
                <div className="event-detail-section" aria-label="相关来源">
                  <h3>相关来源</h3>
                  {relatedMembers.length > 0 ? (
                    relatedMembers.map((member) => (
                      <SourceEvidenceLink key={member.id} item={member} relation={memberRelation(member)} />
                    ))
                  ) : (
                    <p className="hint">暂无更多相关来源。</p>
                  )}
                </div>
                <div className="event-detail-section" aria-label="证据链">
                  <h3>证据链</h3>
                  <ol className="event-evidence-chain">
                    {keyFacts.map((fact) => <li key={fact}>{fact}</li>)}
                    {members.map((member) => (
                      <li key={`member-${member.id}`}>
                        {member.isMain ? "主来源" : "相关来源"}：{member.title}
                        {member.sourceName ? ` · ${member.sourceName}` : ""}
                      </li>
                    ))}
                  </ol>
                  {keyFacts.length === 0 && members.length === 0 && <p className="hint">详情暂无证据链条目。</p>}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </motion.article>
  );
}

function formatReason(reason: string) {
  return reason.startsWith("推荐理由") ? reason : `推荐理由：${reason}`;
}

function aiSignalTags(event: PublicEvent): string[] {
  const category = categoryLabel(event.category);
  const tags = event.tags ?? [];
  return unique([category, ...tags.filter((tag) => /模型|产品|Agent|工具|论文|报告|行业|商业|API|OpenAI|GPT|Claude|Gemini|开源|研究|评测/i.test(tag)), ...tags]).slice(0, 8);
}

function amazonSignalTags(event: PublicEvent): string[] {
  const action = event.sellerActionLevel ? sellerActionLevelLabel(event.sellerActionLevel) : null;
  const category = categoryLabel(event.category);
  const tags = event.tags ?? [];
  return unique([action, category, ...tags.filter((tag) => /风险|合规|账号|账户|FBA|费用|费率|利润|库存|物流|Listing|广告|政策|赔付|选品|税务/i.test(tag)), ...tags]).slice(0, 8);
}

function unique(values: Array<string | null | undefined>): string[] {
  return values.filter((value, index, list): value is string => Boolean(value) && list.indexOf(value) === index);
}

function tagClass(tag: string) {
  if (/风险|合规|账号|账户|费用|费率|利润|税务/.test(tag)) return "tag-risk";
  if (/行动|建议|广告|Listing|FBA|库存|物流|赔付|API/.test(tag)) return "tag-action";
  if (/OpenAI|GPT|Claude|Gemini|Amazon|SP-API/i.test(tag)) return "tag-keyword";
  return "tag-normal";
}

function SourceEvidenceLink({ item, relation }: { item: MainItem | EventMember; relation: string }) {
  const body = (
    <>
      <strong>{item.title}</strong>
      <span>{sourceMeta(item, relation)}</span>
    </>
  );

  if (!item.url) {
    return <div className="event-source-link event-source-link-muted">{body}</div>;
  }

  return (
    <a className="event-source-link" href={item.url} target="_blank" rel="noreferrer">
      {body}
    </a>
  );
}

function sourceMeta(item: MainItem | EventMember, relation: string): string {
  const meta = [item.sourceName ?? "未知来源", relation, sourceGroupLabel(item.sourceGroup), item.sourceTier]
    .filter(Boolean)
    .join(" · ");
  const publishedAt = item.publishedAt ? ` · ${formatDateTime(item.publishedAt)}` : "";
  return `${meta}${publishedAt}`;
}

function memberRelation(member: EventMember): string {
  const relation = member.isMain ? "主来源" : "相关来源";
  return typeof member.relationScore === "number" ? `${relation} · 关联 ${Math.round(member.relationScore)}` : relation;
}
