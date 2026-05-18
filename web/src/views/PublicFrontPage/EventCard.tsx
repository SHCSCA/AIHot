import { useState } from "react";
import { motion } from "framer-motion";
import { ExternalLink, RefreshCw } from "lucide-react";
import type { PublicApi } from "../../api";
import type { PublicEvent, PublicEventDetail } from "../../types";
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
  const { data: detail, reload, loading } = useAsyncData<PublicEventDetail | null>(
    () => (open && api ? api.getEventDetail(event.id) : Promise.resolve(null)),
    null,
    [open, event.id]
  );

  const summary = event.summary || event.mainItem?.summary || "待 AI 处理后生成中文摘要。";
  const reason = formatReason(event.entryReason || event.suggestedAction || `来自 ${event.sourceCount} 个来源，系统评分达到精选阈值。`);

  const scoreClass = event.score > 85 ? "score-high" : event.score >= 70 ? "score-mid" : "score-low";

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

      <div className="aihot-event-card glass">
        <div className="event-meta dark">
          <span>{event.mainItem?.sourceName ?? "未知来源"}</span>
          {event.socialHandle && <span>{event.socialHandle}</span>}
          <span>{sourceGroupLabel(event.sourceGroup)}</span>
          <span>{categoryLabel(event.category)}</span>
          <span>{formatDateTime(event.lastSeenAt)}</span>
        </div>

        <div className="event-title-row">
          <h2>{event.title}</h2>
          <span className={`score-badge ${scoreClass}`}>
            {Math.round(event.score)}
          </span>
        </div>

        {event.mainItem?.imageUrl && (
          <figure className="event-media">
            <img src={event.mainItem.imageUrl} alt={event.mainItem.imageAlt || event.title} loading="lazy" />
          </figure>
        )}

        <p>{summary}</p>

        {event.tags && event.tags.length > 0 && (
          <div className="event-tags dark" role="list" aria-label="事件标签">
            {event.tags.map((tag: string) => <span className={tagClass(tag)} key={tag} role="listitem">{tag}</span>)}
          </div>
        )}

        <div className="event-reason-highlight">
          <span>{reason}</span>
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
          <button className="ghost dark" onClick={() => { setOpen((current) => !current); if (!open && api) reload(); }}>
            {open ? "收起详情" : "事件详情"}
          </button>
        </div>

        {open && (
          <div className="public-detail dark">
            {loading && <p className="hint">正在加载详情...</p>}
            {detail?.members.map((member) => (
              <a key={member.id} href={member.url || "#"} target="_blank" rel="noreferrer">
                <strong>{member.title}</strong>
                <span>{member.sourceName ?? "未知来源"} · {member.isMain ? "主条目" : "关联条目"}</span>
              </a>
            ))}
          </div>
        )}
      </div>
    </motion.article>
  );
}

function formatReason(reason: string) {
  return reason.startsWith("推荐理由") ? reason : `推荐理由：${reason}`;
}

function tagClass(tag: string) {
  if (/风险|合规|账号|费用/.test(tag)) return "tag-risk";
  if (/行动|广告|Listing|FBA|API/.test(tag)) return "tag-action";
  if (/OpenAI|GPT|Claude|Gemini|Amazon|SP-API/i.test(tag)) return "tag-keyword";
  return "tag-normal";
}