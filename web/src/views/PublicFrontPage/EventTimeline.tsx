import { useCallback, useEffect, useRef, useState } from "react";
import { Virtuoso, type VirtuosoHandle } from "react-virtuoso";
import type { PublicApi } from "../../api";
import type { PublicEvent } from "../../types";
import { PaginationBar } from "../../components/PaginationBar";
import { EventCardExpand } from "./EventCardExpand";

export interface EventTimelineProps {
  api: PublicApi;
  channel: "ai" | "amazon";
  activeMode: "selected" | "all";
  filters: { q: string; category: string; date: string; sourceGroup: string };
  page: number;
  eventVersion: number;
  onPageChange: (page: number) => void;
}

interface EventItemData {
  event: PublicEvent;
  index: number;
  prevLastSeenAt?: string | null;
}

const EVENT_PAGE_SIZE = 20;

export function EventTimeline({
  api,
  channel,
  activeMode,
  filters,
  page,
  eventVersion,
  onPageChange,
}: EventTimelineProps) {
  const virtuosoRef = useRef<VirtuosoHandle>(null);
  const [events, setEvents] = useState<PublicEvent[]>([]);
  const [pageInfo, setPageInfo] = useState({ totalPages: 1, total: 0 });
  const [eventError, setEventError] = useState<string | null>(null);
  const [eventLoading, setEventLoading] = useState(false);
  const prevFiltersRef = useRef<string>("");

  // Scroll position restoration on filter/page changes
  useEffect(() => {
    const filterKey = JSON.stringify(filters);
    if (filterKey !== prevFiltersRef.current && virtuosoRef.current) {
      virtuosoRef.current.scrollTo({ top: 0 });
    }
    prevFiltersRef.current = filterKey;
  }, [filters, page, eventVersion]);

  // Fetch events
  useEffect(() => {
    let active = true;
    setEventLoading(true);
    api
      .listEvents({
        channel,
        mode: activeMode,
        category: filters.category || undefined,
        sourceGroup: filters.sourceGroup || undefined,
        q: filters.q || undefined,
        date: filters.date || undefined,
        window: filters.date || channel === "amazon" ? undefined : 24,
        page,
        pageSize: EVENT_PAGE_SIZE,
      })
      .then((result) => {
        if (!active) return;
        setEvents(result.items);
        const resolvedPage = result.page ?? 1;
        setPageInfo({
          totalPages: result.totalPages ?? (result.hasNext ? resolvedPage + 1 : resolvedPage),
          total: result.total ?? result.count,
        });
        setEventError(null);
      })
      .catch((err: unknown) => {
        if (active) setEventError(err instanceof Error ? err.message : "请求失败");
      })
      .finally(() => {
        if (active) setEventLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api, channel, activeMode, filters.q, filters.category, filters.date, filters.sourceGroup, page, eventVersion]);

  // Build item data with date separator hints
  const itemData: EventItemData[] = events.map((event, index) => ({
    event,
    index,
    prevLastSeenAt: events[index - 1]?.lastSeenAt,
  }));

  const Footer = useCallback(
    () => (
      <div className="timeline-footer">
        <PaginationBar
          page={page}
          totalPages={pageInfo.totalPages}
          onPageChange={onPageChange}
          disabled={eventLoading}
        />
      </div>
    ),
    [page, pageInfo.totalPages, onPageChange, eventLoading],
  );

  return (
    <section className="aihot-timeline" aria-label="虚拟化情报流" data-testid="virtualized-event-feed">
      {eventError && <p className="error" role="alert">{eventError}</p>}
      {eventLoading && events.length === 0 && (
        <div className="skeleton-timeline" aria-label="正在加载" aria-live="polite">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="skeleton-event-card" style={{ animationDelay: `${i * 0.12}s` }}>
              <div className="skeleton-timeline-stamp">
                <div className="skeleton-shimmer skeleton-date" />
                <div className="skeleton-shimmer skeleton-time" />
              </div>
              <div className="skeleton-card-body">
                <div className="skeleton-shimmer skeleton-meta" />
                <div className="skeleton-shimmer skeleton-title" />
                <div className="skeleton-shimmer skeleton-text" />
                <div className="skeleton-shimmer skeleton-text short" />
              </div>
            </div>
          ))}
        </div>
      )}
      {!eventLoading && events.length === 0 && (
        <p className="hint" role="status">
          {channel === "amazon"
            ? "Amazon 情报最近 7 天暂无通过质量筛选的公开事件，可切换日期或查看信源墙。"
            : "暂无符合条件的信息。"}
        </p>
      )}
      {events.length > 0 && (
        <Virtuoso
          ref={virtuosoRef}
          data={itemData}
          itemContent={(index, item) => (
            <EventCardExpand
              key={item.event.id}
              event={item.event}
              api={api}
              index={index}
              showDate={index === 0 || !item.prevLastSeenAt || !sameDay(item.prevLastSeenAt, item.event.lastSeenAt ?? "")}
            />
          )}
          useWindowScroll
          increaseViewportBy={{ top: 400, bottom: 400 }}
          defaultItemHeight={260}
          initialItemCount={Math.min(itemData.length, EVENT_PAGE_SIZE)}
        />
      )}
      {events.length > 0 && (
        <div className="timeline-footer">
          <PaginationBar
            page={page}
            totalPages={pageInfo.totalPages}
            onPageChange={onPageChange}
            disabled={eventLoading}
          />
        </div>
      )}
    </section>
  );
}

function EventItem({ event, showDateSeparator }: { event: PublicEvent; showDateSeparator: boolean }) {
  const [open, setOpen] = useState(false);

  return (
    <article className="aihot-event" aria-label={`事件: ${event.title}`}>
      <div className="timeline-stamp dark" aria-hidden="true">
        {showDateSeparator && <span className="timeline-date">{formatMonthDay(event.lastSeenAt ?? "")}</span>}
        <strong>{formatTime(event.lastSeenAt ?? "")}</strong>
        <i />
      </div>
      <div className="aihot-event-card">
        <div className="event-meta dark" aria-label="事件元信息">
          <span>{event.mainItem?.sourceName ?? "未知来源"}</span>
          {event.socialHandle && <span>{event.socialHandle}</span>}
          <span>{event.sourceGroup}</span>
          <span>{event.category}</span>
          <time dateTime={event.lastSeenAt ?? undefined}>{formatDateTime(event.lastSeenAt ?? "")}</time>
        </div>
        <div className="event-title-row">
          <h2>{event.title}</h2>
          <strong className="score-badge" aria-label={`精选分 ${Math.round(event.score)}`}>
            精选分 {Math.round(event.score)}
          </strong>
        </div>
        {event.mainItem?.imageUrl && (
          <figure className="event-media event-media-natural">
            <img src={event.mainItem.imageUrl} alt={event.mainItem.imageAlt || event.title} loading="lazy" />
          </figure>
        )}
        <p>{event.summary || event.mainItem?.summary || "待 AI 处理后生成中文摘要。"}</p>
        {event.tags && event.tags.length > 0 && (
          <div className="event-tags dark" role="list" aria-label="标签">
            {event.tags.map((tag: string) => <span className={tagClass(tag)} key={tag} role="listitem">{tag}</span>)}
          </div>
        )}
        <div className="event-reason-highlight" aria-label="推荐理由">
          <span>{formatReason(event.entryReason || event.suggestedAction || `来自 ${event.sourceCount} 个来源，系统评分达到精选阈值。`)}</span>
          {event.sellerActionLevel && <em>{event.sellerActionLevel}</em>}
          {event.confidenceScore != null && <em>置信度 {Math.round(event.confidenceScore)}</em>}
        </div>
        <div className="event-foot" role="group" aria-label="事件操作">
          <span>{event.sourceCount} 个来源</span>
          <span>{event.memberCount} 条相关</span>
          {event.mainItem?.url && (
            <a href={event.mainItem.url} target="_blank" rel="noreferrer" aria-label="查看原文">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              查看原文
            </a>
          )}
          <button
            className="ghost dark"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            aria-controls={`event-detail-${event.id}`}
          >
            {open ? "收起详情" : "事件详情"}
          </button>
        </div>
        {open && (
          <div id={`event-detail-${event.id}`} className="public-detail dark" aria-label="事件详情">
            <p className="hint" aria-live="polite">正在加载详情...</p>
          </div>
        )}
      </div>
    </article>
  );
}

function formatMonthDay(dateStr: string | null | undefined): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  return `${d.getMonth() + 1}月${d.getDate()}日`;
}

function formatTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function sameDay(a: string | null | undefined, b: string | null | undefined): boolean {
  if (!a || !b) return false;
  return a.slice(0, 10) === b.slice(0, 10);
}

function formatReason(reason: string): string {
  return reason.startsWith("推荐理由") ? reason : `推荐理由：${reason}`;
}

function tagClass(tag: string): string {
  if (/风险|合规|账号|费用/.test(tag)) return "tag-risk";
  if (/行动|广告|Listing|FBA|API/.test(tag)) return "tag-action";
  if (/OpenAI|GPT|Claude|Gemini|Amazon|SP-API/i.test(tag)) return "tag-keyword";
  return "tag-normal";
}
