/**
 * Skeleton loading components with shimmer animation.
 * Used for EventCard, DailyReader, SourceWall placeholders.
 */

export interface SkeletonCardProps {
  /** Optional custom class for the card wrapper */
  className?: string;
  /** Animation delay in seconds */
  delay?: number;
}

/**
 * Skeleton card with shimmer animation that mimics the EventCard layout.
 */
export function SkeletonCard({ className = "", delay = 0 }: SkeletonCardProps) {
  return (
    <div className={`skeleton-event-card ${className}`} style={{ animationDelay: `${delay}s` }} aria-hidden="true">
      <div className="skeleton-timeline-stamp">
        <div className="skeleton-shimmer skeleton-date" />
        <div className="skeleton-shimmer skeleton-time" />
      </div>
      <div className="skeleton-card-body">
        <div className="skeleton-shimmer skeleton-meta" />
        <div className="skeleton-shimmer skeleton-title" />
        <div className="skeleton-shimmer skeleton-text" />
        <div className="skeleton-shimmer skeleton-text short" />
        <div className="skeleton-shimmer skeleton-text very-short" />
      </div>
    </div>
  );
}

/**
 * Skeleton for SourceWall cards.
 */
export function SkeletonSourceCard({ delay = 0 }: { delay?: number }) {
  return (
    <div className="skeleton-source-card" style={{ animationDelay: `${delay}s` }} aria-hidden="true">
      <div className="skeleton-card-top">
        <div className="skeleton-shimmer skeleton-source-name" />
        <div className="skeleton-shimmer skeleton-source-badge" />
      </div>
      <div className="skeleton-shimmer skeleton-source-meta" />
      <div className="skeleton-shimmer skeleton-source-tags" />
    </div>
  );
}

/**
 * Skeleton for DailyReader stories.
 */
export function SkeletonDailyStory({ delay = 0 }: { delay?: number }) {
  return (
    <div className="skeleton-daily-story" style={{ animationDelay: `${delay}s` }} aria-hidden="true">
      <div className="skeleton-shimmer skeleton-daily-title" />
      <div className="skeleton-shimmer skeleton-daily-meta" />
      <div className="skeleton-shimmer skeleton-daily-text" />
      <div className="skeleton-shimmer skeleton-daily-text short" />
    </div>
  );
}

/**
 * Multiple skeleton cards for list loading states.
 */
export interface SkeletonListProps {
  count?: number;
  /** Variant: 'event' | 'source' | 'daily' */
  variant?: "event" | "source" | "daily";
}

export function SkeletonList({ count = 3, variant = "event" }: SkeletonListProps) {
  return (
    <>
      {[...Array(count)].map((_, i) => {
        if (variant === "source") return <SkeletonSourceCard key={i} delay={i * 0.1} />;
        if (variant === "daily") return <SkeletonDailyStory key={i} delay={i * 0.1} />;
        return <SkeletonCard key={i} delay={i * 0.12} />;
      })}
    </>
  );
}