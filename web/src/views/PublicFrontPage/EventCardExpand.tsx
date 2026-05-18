import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import type { PublicEvent, PublicEventDetail } from "../../types";
import { useAsyncData } from "../../hooks";
import { ExternalLink } from "lucide-react";
import { formatDateTime, formatMonthDay, formatTime } from "../../utils";
import {
  categoryLabel,
  sourceGroupLabel,
  sellerActionLevelLabel
} from "../../labels";

interface EventCardExpandProps {
  event: PublicEvent;
  api: { getEventDetail: (id: string) => Promise<PublicEventDetail | null> };
  showDate: boolean;
  index: number;
}

export function EventCardExpand({ event, api, showDate, index }: EventCardExpandProps) {
  const [open, setOpen] = useState(false);
  const { data: detail, reload, loading } = useAsyncData<PublicEventDetail | null>(
    () => (open ? api.getEventDetail(event.id) : Promise.resolve(null)),
    null,
    [open, event.id]
  );

  const summary = event.summary || event.mainItem?.summary || "待 AI 处理后生成中文摘要。";
  const reason = formatReason(event.entryReason || event.suggestedAction || `来自 ${event.sourceCount} 个来源，系统评分达到精选阈值。`);

  const allVariants = {
    hidden: { opacity: 0, y: 12, scale: 0.98 },
    visible: (i: number) => ({
      opacity: 1,
      y: 0,
      scale: 1,
      transition: {
        delay: i * 0.04,
        duration: 0.35,
        ease: [0.4, 0, 0.2, 1] as [number, number, number, number],
      },
    }),
    exit: { opacity: 0, scale: 0.96, transition: { duration: 0.2 } },
  };

  return (
    <motion.article
      className="aihot-event"
      layout
      custom={index}
      variants={allVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
    >
      <div className="timeline-stamp dark">
        {showDate && <span className="timeline-date">{formatMonthDay(event.lastSeenAt)}</span>}
        <strong>{formatTime(event.lastSeenAt)}</strong>
        <i aria-hidden="true" />
      </div>
      <motion.div layoutId={`event-card-${event.id}`} className="aihot-event-card">
        <motion.div layoutId={`event-meta-${event.id}`} className="event-meta dark">
          <span>{event.mainItem?.sourceName ?? "未知来源"}</span>
          {event.socialHandle && <span>{event.socialHandle}</span>}
          <span>{sourceGroupLabel(event.sourceGroup)}</span>
          <span>{categoryLabel(event.category)}</span>
          <span>{formatDateTime(event.lastSeenAt)}</span>
        </motion.div>

        <div className="event-title-row">
          <motion.h2 layoutId={`event-title-${event.id}`}>{event.title}</motion.h2>
          <strong className="score-badge">精选分 {Math.round(event.score)}</strong>
        </div>

        {event.mainItem?.imageUrl && (
          <figure className="event-media event-media-natural">
            <img src={event.mainItem.imageUrl} alt={event.mainItem.imageAlt || event.title} loading="lazy" />
          </figure>
        )}

        <motion.p layoutId={`event-summary-${event.id}`}>{summary}</motion.p>

        {event.tags && event.tags.length > 0 && (
          <motion.div layoutId={`event-tags-${event.id}`} className="event-tags dark">
            {event.tags.map((tag) => <span className={tagClass(tag)} key={tag}>{tag}</span>)}
          </motion.div>
        )}

        <div className="event-reason-highlight">
          <span>{reason}</span>
          {event.sellerActionLevel && <em>{sellerActionLevelLabel(event.sellerActionLevel)}</em>}
          {event.confidenceScore != null && <em>置信度 {Math.round(event.confidenceScore)}</em>}
        </div>

        <motion.div layoutId={`event-foot-${event.id}`} className="event-foot">
          <span>{event.sourceCount} 个来源</span>
          <span>{event.memberCount} 条相关</span>
          {event.mainItem?.url && (
            <a href={event.mainItem.url} target="_blank" rel="noreferrer">
              <ExternalLink size={15} />查看原文
            </a>
          )}
          <button
            className="ghost dark"
            onClick={() => {
              setOpen((current) => !current);
              if (!open) reload();
            }}
          >
            {open ? "收起详情" : "事件详情"}
          </button>
        </motion.div>

        <AnimatePresence>
          {open && (
            <motion.div
              layoutId={`event-detail-${event.id}`}
              className="public-detail dark"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.45, ease: [0.4, 0, 0.2, 1] }}
            >
              {loading && <p className="hint">正在加载详情...</p>}
              {detail?.members.map((member) => (
                <a key={member.id} href={member.url} target="_blank" rel="noreferrer">
                  <strong>{member.title}</strong>
                  <span>{member.sourceName ?? "未知来源"} · {member.isMain ? "主条目" : "关联条目"}</span>
                </a>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
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