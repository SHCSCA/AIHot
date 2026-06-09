import { useEffect, useRef, useState } from "react";
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
    prevLastSeenAt: events[index - 1]?.lastSeenAt,
  }));

  return (
    <section className="aihot-timeline" aria-label="虚拟化情报流" data-testid="virtualized-event-feed" data-loading={eventLoading ? "true" : "false"}>
      {eventError && <p className="error" role="alert">{eventError}</p>}
      {eventLoading && events.length > 0 && <p className="timeline-loading-chip" aria-live="polite">正在刷新情报流...</p>}
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

function sameDay(a: string | null | undefined, b: string | null | undefined): boolean {
  if (!a || !b) return false;
  return a.slice(0, 10) === b.slice(0, 10);
}
