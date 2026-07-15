import { motion, useReducedMotion } from "framer-motion";
import {
  ArrowRight,
  BookOpenText,
  Clock3,
  Newspaper,
  RadioTower,
  SignalHigh,
  Sparkles,
  Store
} from "lucide-react";
import { categoryLabel, sourceGroupLabel } from "../../labels";
import type { PublicEvent } from "../../types";
import { formatDateTime } from "../../utils";

type PublicChannel = "ai" | "amazon";

type BriefConfig = {
  eyebrow: string;
  title: string;
  summary: string;
  windowLabel: string;
  sourceState: string;
  emptyTitle: string;
  emptyDetail: string;
  focus: string[];
};

const briefConfig: Record<PublicChannel, BriefConfig> = {
  ai: {
    eyebrow: "Reader Mode · AI Brief",
    title: "今日 AI 情报 Brief",
    summary: "从模型、产品、Agent、论文与产业变化中，先给出值得判断的事件，再展开证据。",
    windowLabel: "最近 24 小时",
    sourceState: "AI 信源池",
    emptyTitle: "高信号事件仍在汇聚",
    emptyDetail: "当前没有可公开展示的精选事件，可进入全部动态查看最新采集结果。",
    focus: ["模型与能力边界", "Agent 与开发者工作流", "评测、论文与商业化信号"]
  },
  amazon: {
    eyebrow: "Reader Mode · Seller Brief",
    title: "今日 Amazon 卖家 Brief",
    summary: "从政策、账号、FBA、广告与成本变化中，先呈现需要判断和行动的运营信号。",
    windowLabel: "最近 7 天",
    sourceState: "卖家信源池",
    emptyTitle: "卖家行动信号仍在汇聚",
    emptyDetail: "当前没有可公开展示的精选事件，可进入全部热点核对最近采集结果。",
    focus: ["政策与账号健康", "FBA、物流与费用", "广告、Listing 与选品机会"]
  }
};

type HeroSectionProps = {
  channel: PublicChannel;
  sourceCount?: number;
  events: PublicEvent[];
  loading: boolean;
  error: string | null;
  onOpenSelected: () => void;
  onOpenAll: () => void;
  onOpenDaily: () => void;
};

export function HeroSection({
  channel,
  sourceCount,
  events,
  loading,
  error,
  onOpenSelected,
  onOpenAll,
  onOpenDaily
}: HeroSectionProps) {
  const reducedMotion = useReducedMotion();
  const brief = briefConfig[channel];
  const lead = events[0];
  const shifts = events.slice(1, 4);
  const ChannelIcon = channel === "ai" ? Sparkles : Store;
  const resolvedSourceCount = sourceCount == null ? "同步中" : sourceCount.toLocaleString();
  const updatedAt = lead?.lastSeenAt ? formatDateTime(lead.lastSeenAt) : "等待新事件";
  const enter = reducedMotion
    ? { duration: 0 }
    : { duration: 0.34, ease: [0.22, 1, 0.36, 1] as [number, number, number, number] };

  return (
    <section className="hero-section qi-brief" aria-label="AIHOT 情报总览">
      <header className="qi-brief-header">
        <div>
          <p className="brief-eyebrow"><ChannelIcon size={15} />{brief.eyebrow}</p>
          <h1>{brief.title}</h1>
          <p>{brief.summary}</p>
        </div>
        <dl className="qi-brief-status" aria-label="当前情报状态">
          <div><dt><Clock3 size={14} />观察窗口</dt><dd>{brief.windowLabel}</dd></div>
          <div><dt><RadioTower size={14} />{brief.sourceState}</dt><dd>{resolvedSourceCount}</dd></div>
          <div><dt><SignalHigh size={14} />最近更新</dt><dd>{updatedAt}</dd></div>
        </dl>
      </header>

      <div className="qi-brief-layout">
        <motion.article
          className="qi-brief-lead liquid-glass-floating"
          initial={reducedMotion ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={enter}
        >
          <div className="qi-brief-lead-meta">
            <span>首要事件</span>
            {lead && <strong>精选 {Math.round(lead.score)}</strong>}
          </div>

          {loading && !lead ? (
            <div className="qi-brief-loading" role="status" aria-live="polite">
              <span />
              <span />
              <span />
              <p>正在整理今日高信号事件...</p>
            </div>
          ) : (
            <>
              <h2>{lead?.title ?? brief.emptyTitle}</h2>
              <p className="qi-brief-lead-summary">{lead?.summary || brief.emptyDetail}</p>
              {lead && (
                <div className="qi-brief-event-meta" aria-label="首要事件信息">
                  <span>{lead.mainItem?.sourceName ?? "来源待核对"}</span>
                  <span>{categoryLabel(lead.category)}</span>
                  <span>{sourceGroupLabel(lead.sourceGroup)}</span>
                  <span>{lead.sourceCount} 个来源</span>
                </div>
              )}
              <div className="qi-brief-why">
                <span>为什么重要</span>
                <p>{lead?.entryReason?.replace(/^推荐理由[：:]\s*/, "") || lead?.suggestedAction || "进入事件流查看来源、上下文与建议动作。"}</p>
              </div>
            </>
          )}

          {error && <p className="qi-brief-error" role="alert">Brief 获取失败：{error}</p>}
          <div className="qi-brief-actions" aria-label="Brief 阅读入口">
            <button className="primary" onClick={onOpenSelected}>阅读精选 <ArrowRight size={16} /></button>
            <button className="ghost" onClick={onOpenAll}>查看全部</button>
          </div>
        </motion.article>

        <motion.aside
          className="qi-brief-shifts liquid-glass-panel"
          initial={reducedMotion ? false : { opacity: 0, x: 10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ ...enter, delay: reducedMotion ? 0 : 0.06 }}
          aria-labelledby="brief-shifts-title"
        >
          <div className="qi-brief-shifts-heading">
            <div>
              <span>KEY SHIFTS</span>
              <h2 id="brief-shifts-title">本轮关注</h2>
            </div>
            <BookOpenText size={19} aria-hidden="true" />
          </div>

          <ol className="qi-shift-list">
            {(shifts.length > 0 ? shifts : brief.focus).map((item, index) => {
              const event = typeof item === "string" ? null : item;
              const itemKey = typeof item === "string" ? item : item.id;
              const itemTitle = typeof item === "string" ? item : item.title;
              return (
                <li key={itemKey}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <strong>{itemTitle}</strong>
                    <p>{event?.summary || (loading ? "正在核对相关信号..." : "进入精选事件流查看对应证据与行动建议。")}</p>
                  </div>
                </li>
              );
            })}
          </ol>

          <button className="qi-daily-link" onClick={onOpenDaily}>
            <Newspaper size={16} />打开今日日报<ArrowRight size={15} />
          </button>
        </motion.aside>
      </div>
    </section>
  );
}
