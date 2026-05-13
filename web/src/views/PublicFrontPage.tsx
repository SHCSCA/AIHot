import { ExternalLink, LockKeyhole, RefreshCw, Rss, Search, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import type { Credentials, PublicApi } from "../api";
import { categoryLabel, channelLabel, modeLabel, sellerActionLevelLabel } from "../labels";
import type { PublicDaily, PublicEvent, PublicEventDetail, PublicFeedLink } from "../types";
import { formatDateTime, formatMonthDay, formatTime, today } from "../utils";
import { useAsyncData } from "../hooks";

type PublicChannel = "ai" | "amazon";
type PublicSection = "selected" | "all" | "daily" | "rss";

const channels: Record<PublicChannel, { title: string; heading: string; description: string; scope: string }> = {
  ai: {
    title: "AI 热点",
    heading: "AI 热点",
    description: "追踪模型、产品、Agent、论文和行业变化，按事件聚合成中文可读的信息流。",
    scope: "模型、产品、行业、论文、技巧"
  },
  amazon: {
    title: "亚马逊情报",
    heading: "亚马逊卖家情报",
    description: "追踪 SP-API、广告、账号健康、FBA、选品和运营变化，服务卖家决策。",
    scope: "平台政策、广告、物流、选品、账号风控"
  }
};

const feedLinks: Array<PublicFeedLink & { channel: PublicChannel }> = [
  { channel: "ai", label: "AI 事件 RSS", url: "/feed/ai/events.xml", description: "订阅 AI 热点事件流" },
  { channel: "ai", label: "AI 日报 RSS", url: "/feed/ai/daily.xml", description: "订阅 AI 每日精选" },
  { channel: "amazon", label: "亚马逊事件 RSS", url: "/feed/amazon/events.xml", description: "订阅亚马逊情报事件流" },
  { channel: "amazon", label: "亚马逊日报 RSS", url: "/feed/amazon/daily.xml", description: "订阅亚马逊每日精选" }
];

export function PublicFrontPage({
  api,
  loginError,
  loginOpen,
  onLogin
}: {
  api: PublicApi;
  loginError: string | null;
  loginOpen: boolean;
  onLogin: (credentials: Credentials) => Promise<void>;
}) {
  const [channel, setChannel] = useState<PublicChannel>("ai");
  const [section, setSection] = useState<PublicSection>("selected");
  const [showLogin, setShowLogin] = useState(loginOpen);
  const [filters, setFilters] = useState({ q: "", category: "", date: "" });
  const [events, setEvents] = useState<PublicEvent[]>([]);
  const [eventError, setEventError] = useState<string | null>(null);
  const [eventLoading, setEventLoading] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasNext, setHasNext] = useState(false);
  const [eventVersion, setEventVersion] = useState(0);
  const activeMode = section === "all" ? "all" : "selected";
  const activeChannel = channels[channel];

  useEffect(() => {
    let active = true;
    setEventLoading(true);
    api
      .listEvents({
        channel,
        mode: activeMode,
        category: filters.category || undefined,
        q: filters.q || undefined,
        date: filters.date || undefined,
        window: filters.date ? undefined : 24,
        take: section === "all" ? 32 : 18
      })
      .then((page) => {
        if (!active) return;
        setEvents(page.items);
        setNextCursor(page.nextCursor);
        setHasNext(page.hasNext);
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
  }, [api, channel, section, activeMode, filters.q, filters.category, filters.date, eventVersion]);

  async function loadMoreEvents() {
    if (!nextCursor || eventLoading) return;
    setEventLoading(true);
    try {
      const page = await api.listEvents({
        channel,
        mode: activeMode,
        category: filters.category || undefined,
        q: filters.q || undefined,
        date: filters.date || undefined,
        window: filters.date ? undefined : 24,
        take: section === "all" ? 32 : 18,
        cursor: nextCursor
      });
      setEvents((current) => [...current, ...page.items]);
      setNextCursor(page.nextCursor);
      setHasNext(page.hasNext);
      setEventError(null);
    } catch (err) {
      setEventError(err instanceof Error ? err.message : "请求失败");
    } finally {
      setEventLoading(false);
    }
  }

  return (
    <main className="public-shell">
      <header className="public-header">
        <div className="public-brand">
          <span className="brand-dot"><Sparkles size={18} /></span>
          <strong>AI 热点情报</strong>
        </div>
        <nav aria-label="频道分区" className="public-nav public-channel-nav">
          <button className={channel === "ai" ? "active" : ""} onClick={() => setChannel("ai")}>AI 热点</button>
          <button className={channel === "amazon" ? "active" : ""} onClick={() => setChannel("amazon")}>亚马逊情报</button>
        </nav>
        <button className="login-trigger" onClick={() => setShowLogin((current) => !current)}><LockKeyhole size={16} />运营登录</button>
      </header>

      <section className="public-hero">
        <div>
          <p className="eyebrow">中文情报前台 · {activeChannel.scope}</p>
          <h1>{activeChannel.heading}</h1>
          <p>{activeChannel.description}</p>
        </div>
        <div className="hero-metrics" aria-label="前台概览">
          <span><strong>{events.length}</strong>当前结果</span>
          <span><strong>{modeLabel(activeMode)}</strong>当前模式</span>
          <span><strong>最近 24 小时</strong>滚动窗口</span>
        </div>
      </section>

      {showLogin && <PublicLoginPanel error={loginError} onLogin={onLogin} />}

      <nav aria-label="频道内功能" className="public-section-nav">
        <button className={section === "selected" ? "active" : ""} onClick={() => setSection("selected")}>精选</button>
        <button className={section === "all" ? "active" : ""} onClick={() => setSection("all")}>全部热点</button>
        <button className={section === "daily" ? "active" : ""} onClick={() => setSection("daily")}>日报</button>
        <button className={section === "rss" ? "active" : ""} onClick={() => setSection("rss")}>RSS 订阅</button>
      </nav>

      {section === "daily" ? (
        <DailyReader api={api} channel={channel} />
      ) : section === "rss" ? (
        <RssLinks channel={channel} />
      ) : (
        <section className="public-content">
          <aside className="public-filters">
            <label><Search size={15} />关键词<input value={filters.q} onChange={(event) => setFilters({ ...filters, q: event.target.value })} placeholder="搜索标题或摘要" /></label>
            <label>分类<select value={filters.category} onChange={(event) => setFilters({ ...filters, category: event.target.value })}><option value="">全部分类</option>{categoryOptions(channel).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
            <label>指定日期<input type="date" value={filters.date} onChange={(event) => setFilters({ ...filters, date: event.target.value })} /></label>
            <p className="hint">当前展示最近 24 小时情报；指定日期后按该日历史分页查看。</p>
            <button className="ghost" onClick={() => setEventVersion((current) => current + 1)}><RefreshCw size={15} />刷新</button>
          </aside>
          <section className="event-feed" aria-label="热点信息流">
            {eventError && <p className="error">{eventError}</p>}
            {eventLoading && events.length === 0 && <p className="hint">正在加载中文情报...</p>}
            {events.map((event, index) => (
              <PublicEventCard
                key={event.id}
                event={event}
                api={api}
                showDate={index === 0 || formatMonthDay(events[index - 1]?.lastSeenAt) !== formatMonthDay(event.lastSeenAt)}
              />
            ))}
            {!eventLoading && events.length === 0 && <p className="hint">暂无符合条件的信息。</p>}
            {hasNext && <button className="load-more" onClick={loadMoreEvents} disabled={eventLoading}>{eventLoading ? "正在加载..." : "加载更多"}</button>}
          </section>
        </section>
      )}
    </main>
  );
}

function PublicLoginPanel({ error, onLogin }: { error: string | null; onLogin: (credentials: Credentials) => Promise<void> }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    setSubmitting(true);
    try {
      await onLogin({ username, password });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="public-login-panel">
      <div><ShieldCheck size={19} /><strong>运营后台登录</strong><span>登录后进入信源、事件、日报和策略管理台。</span></div>
      <label>管理员账号<input aria-label="管理员账号" value={username} onChange={(event) => setUsername(event.target.value)} /></label>
      <label>管理员密码<input aria-label="管理员密码" type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
      {error && <p className="error">{error}</p>}
      <button className="primary" onClick={submit} disabled={submitting}>登录</button>
    </section>
  );
}

function PublicEventCard({ event, api, showDate }: { event: PublicEvent; api: PublicApi; showDate: boolean }) {
  const [open, setOpen] = useState(false);
  const { data: detail, reload, loading } = useAsyncData<PublicEventDetail | null>(
    () => (open ? api.getEventDetail(event.id) : Promise.resolve(null)),
    null,
    [open, event.id]
  );
  const summary = event.summary || event.mainItem?.summary || "待 AI 处理后生成中文摘要。";
  const reason = event.entryReason || event.suggestedAction || `来自 ${event.sourceCount} 个来源，系统评分达到精选阈值。`;

  return (
    <article className="public-event">
      <div className="timeline-stamp">
        {showDate && <span className="timeline-date">{formatMonthDay(event.lastSeenAt)}</span>}
        <strong>{formatTime(event.lastSeenAt)}</strong>
        <i aria-hidden="true" />
      </div>
      <div className="event-main">
        <div className="event-meta">
          <span>{channelLabel(event.channel)}</span>
          <span>{categoryLabel(event.category)}</span>
          <span>{event.mainItem?.sourceName ?? "未知来源"}</span>
          <span>{formatDateTime(event.lastSeenAt)}</span>
          <span>精选分 {Math.round(event.score)}</span>
        </div>
        <h2>{event.title}</h2>
        <p>{summary}</p>
        <div className="event-reason">
          <span>推荐理由：{reason}</span>
          {event.sellerActionLevel && <span>{sellerActionLevelLabel(event.sellerActionLevel)}</span>}
          {event.confidenceScore != null && <span>置信度 {Math.round(event.confidenceScore)}</span>}
          <span>{event.sourceCount} 个来源</span>
          <span>{event.memberCount} 条相关</span>
        </div>
        {event.tags && event.tags.length > 0 && (
          <div className="event-tags">
            {event.tags.map((tag) => <span key={tag}>{tag}</span>)}
          </div>
        )}
        <div className="inline-actions">
          {event.mainItem?.url && <a href={event.mainItem.url} target="_blank" rel="noreferrer"><ExternalLink size={15} />查看原文</a>}
          <button className="ghost" onClick={() => { setOpen((current) => !current); if (!open) reload(); }}>{open ? "收起详情" : "事件详情"}</button>
        </div>
        {open && (
          <div className="public-detail">
            {loading && <p className="hint">正在加载详情...</p>}
            {detail?.members.map((member) => (
              <a key={member.id} href={member.url} target="_blank" rel="noreferrer">
                <strong>{member.title}</strong>
                <span>{member.sourceName ?? "未知来源"} · {member.isMain ? "主条目" : "关联条目"}</span>
              </a>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

function DailyReader({ api, channel }: { api: PublicApi; channel: PublicChannel }) {
  const [date, setDate] = useState(today());
  const { data: daily, error, loading, reload } = useAsyncData<PublicDaily | null>(() => api.getDaily({ channel, date }), null, [channel, date]);
  const highlights = dailyHighlights(daily);

  return (
    <section className="daily-reader">
      <div className="public-filters horizontal">
        <label>频道<input value={channels[channel].title} readOnly /></label>
        <label>日期<input type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label>
        <button className="ghost" onClick={reload}>刷新日报</button>
      </div>
      {error && <p className="error">{error}</p>}
      {loading && !daily && <p className="hint">正在读取日报...</p>}
      {daily ? (
        <article className="daily-document">
          <p className="eyebrow">{channelLabel(daily.channel)} · {daily.date}</p>
          <h2>{daily.title}</h2>
          <p className="hint">{daily.windowLabel || "基于最近 24 小时精选情报自动生成"}</p>
          {highlights.map((item, index) => (
            <section className="daily-timeline-item" key={item.eventId || item.title}>
              <div className="timeline-stamp compact">
                {index === 0 && <span className="timeline-date">{formatMonthDay(String(item.lastSeenAt ?? daily.generatedAt))}</span>}
                <strong>{formatTime(String(item.lastSeenAt ?? daily.generatedAt))}</strong>
                <i aria-hidden="true" />
              </div>
              <div>
                <strong>{item.title}</strong>
                <p>{String(item.summary ?? "待 AI 处理后生成中文摘要。")}</p>
                <span>{categoryLabel(String(item.category ?? ""))} · 精选分 {Math.round(Number(item.score ?? 0))}</span>
                <span>推荐理由：{String(item.entryReason ?? "待 AI 处理后生成推荐理由。")}</span>
              </div>
            </section>
          ))}
        </article>
      ) : !loading && <p className="hint">这一天还没有已发布日报。</p>}
    </section>
  );
}

function RssLinks({ channel }: { channel: PublicChannel }) {
  const links = feedLinks.filter((link) => link.channel === channel);
  return (
    <section className="rss-grid">
      {links.map((link) => (
        <a key={link.url} href={link.url} target="_blank" rel="noreferrer">
          <Rss size={18} />
          <strong>{link.label}</strong>
          <span>{link.description}</span>
        </a>
      ))}
    </section>
  );
}

function categoryOptions(channel: PublicChannel) {
  if (channel === "amazon") {
    return [
      { value: "policy", label: "政策监管" },
      { value: "account_health", label: "账号健康" },
      { value: "fba_logistics", label: "FBA 物流" },
      { value: "ads_ppc", label: "广告投放" },
      { value: "listing_seo", label: "Listing 与搜索" },
      { value: "fees_margin", label: "费用利润" },
      { value: "product_research", label: "选品研究" },
      { value: "tools", label: "卖家工具" },
      { value: "compliance_trade", label: "合规贸易" }
    ];
  }
  return [
    { value: "ai_models", label: "AI 模型" },
    { value: "ai_products", label: "AI 产品" },
    { value: "agent_tools", label: "Agent 与工具" },
    { value: "papers", label: "论文报告" },
    { value: "industry", label: "行业观察" },
    { value: "monetization", label: "商业变现" }
  ];
}

function dailyHighlights(daily: PublicDaily | null) {
  const sections = daily?.sections;
  if (!sections || !Array.isArray(sections.highlights)) return [] as Array<Record<string, string | number | null>>;
  return sections.highlights.filter((item): item is Record<string, string | number | null> => Boolean(item) && typeof item === "object");
}
