import {
  ExternalLink,
  Heart,
  List,
  LockKeyhole,
  MessageCircle,
  Newspaper,
  Plus,
  RefreshCw,
  Rss,
  Search,
  ShieldCheck,
  Sparkles,
  Zap
} from "lucide-react";
import { useEffect, useState } from "react";
import type { Credentials, PublicApi } from "../api";
import {
  categoryLabel,
  channelLabel,
  collectionStatusLabel,
  modeLabel,
  sellerActionLevelLabel,
  sourceGroupLabel,
  sourceTypeLabel
} from "../labels";
import type { PublicDaily, PublicEvent, PublicEventDetail, PublicFeedLink, Source } from "../types";
import { formatDateTime, formatMonthDay, formatTime, today } from "../utils";
import { useAsyncData } from "../hooks";

type PublicChannel = "ai" | "amazon";
type PublicSection = "selected" | "all" | "daily" | "rss" | "sources";

const channels: Record<PublicChannel, { title: string; heading: string; description: string; scope: string }> = {
  ai: {
    title: "AI 热点",
    heading: "全部 AI 动态",
    description: "AI 相关资讯全量信息流",
    scope: "模型、产品、Agent、论文和行业变化"
  },
  amazon: {
    title: "亚马逊情报",
    heading: "全部 Amazon 情报",
    description: "面向卖家的平台、广告、FBA、选品和合规变化",
    scope: "政策、账号、物流、广告、Listing、费用和选品"
  }
};

const sectionItems: Array<{ id: PublicSection; label: string; Icon: typeof Zap }> = [
  { id: "selected", label: "精选", Icon: Zap },
  { id: "all", label: "全部热点", Icon: List },
  { id: "daily", label: "日报", Icon: Newspaper },
  { id: "rss", label: "RSS 订阅", Icon: Rss },
  { id: "sources", label: "信源墙", Icon: Plus }
];

const sourceGroups = [
  { value: "", label: "全部" },
  { value: "official", label: "官方" },
  { value: "first_party", label: "一手信源" },
  { value: "media", label: "资讯" },
  { value: "social", label: "推文" },
  { value: "community", label: "社区" },
  { value: "vendor", label: "服务商" }
];

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
  const [filters, setFilters] = useState({ q: "", category: "", date: "", sourceGroup: "" });
  const [events, setEvents] = useState<PublicEvent[]>([]);
  const [eventError, setEventError] = useState<string | null>(null);
  const [eventLoading, setEventLoading] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasNext, setHasNext] = useState(false);
  const [eventVersion, setEventVersion] = useState(0);
  const activeMode = section === "all" ? "all" : "selected";
  const activeChannel = channels[channel];

  useEffect(() => {
    if (section === "daily" || section === "rss" || section === "sources") return;
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
  }, [
    api,
    channel,
    section,
    activeMode,
    filters.q,
    filters.category,
    filters.date,
    filters.sourceGroup,
    eventVersion
  ]);

  async function loadMoreEvents() {
    if (!nextCursor || eventLoading) return;
    setEventLoading(true);
    try {
      const page = await api.listEvents({
        channel,
        mode: activeMode,
        category: filters.category || undefined,
        sourceGroup: filters.sourceGroup || undefined,
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

  function switchChannel(next: PublicChannel) {
    setChannel(next);
    setFilters({ q: "", category: "", date: "", sourceGroup: "" });
    setEventVersion((current) => current + 1);
  }

  return (
    <main className="aihot-public-shell">
      <aside className="aihot-sidebar">
        <div className="aihot-logo" aria-label="AI Hot">
          <span>AI</span><i />HOT
        </div>
        <nav aria-label="频道分区" className="aihot-channel-nav">
          <button className={channel === "ai" ? "active" : ""} onClick={() => switchChannel("ai")}>
            <Sparkles size={19} />AI 热点
          </button>
          <button className={channel === "amazon" ? "active" : ""} onClick={() => switchChannel("amazon")}>
            <Heart size={19} />亚马逊情报
          </button>
        </nav>
        <nav aria-label="频道内功能" className="aihot-section-nav">
          {sectionItems.map(({ id, label, Icon }) => (
            <button key={id} className={section === id ? "active" : ""} onClick={() => setSection(id)}>
              <Icon size={19} />{label}
            </button>
          ))}
        </nav>
        <div className="aihot-sidebar-bottom">
          <button type="button" className="theme-dot active" aria-label="深色模式" />
          <button type="button" className="theme-dot" aria-label="桌面模式" />
          <button type="button" className="login-link" onClick={() => setShowLogin((current) => !current)}>
            <LockKeyhole size={16} />后台入口
          </button>
        </div>
      </aside>

      <section className="aihot-workspace">
        <header className="aihot-topbar">
          <div>
            <h1>{section === "selected" ? activeChannel.title : section === "all" ? activeChannel.heading : sectionTitle(section)}</h1>
            <p>{sectionDescription(section, activeChannel.description)} · 当前展示最近 24 小时情报</p>
          </div>
          <div className="aihot-search">
            <Search size={16} />
            <input
              value={filters.q}
              onChange={(event) => setFilters({ ...filters, q: event.target.value })}
              placeholder="搜索标题/摘要..."
            />
            <button onClick={() => setEventVersion((current) => current + 1)}>搜索</button>
          </div>
          <button className="login-trigger dark" onClick={() => setShowLogin((current) => !current)}>
            <LockKeyhole size={16} />运营登录
          </button>
        </header>

        <section className="aihot-channel-context">
          <div>
            <strong>{activeChannel.title}</strong>
            <span>{activeChannel.scope}</span>
          </div>
          <div className="hero-metrics dark">
            <span><strong>{events.length}</strong>当前结果</span>
            <span><strong>{modeLabel(activeMode)}</strong>当前模式</span>
            <span><strong>24</strong>小时窗口</span>
          </div>
        </section>

        {showLogin && <PublicLoginPanel error={loginError} onLogin={onLogin} />}

        {section === "daily" ? (
          <DailyReader api={api} channel={channel} />
        ) : section === "rss" ? (
          <RssLinks channel={channel} />
        ) : section === "sources" ? (
          <SourceWall api={api} channel={channel} />
        ) : (
          <>
            <FilterBar
              channel={channel}
              filters={filters}
              onChange={(next) => setFilters({ ...filters, ...next })}
              onRefresh={() => setEventVersion((current) => current + 1)}
            />
            <section className="aihot-timeline" aria-label="热点信息流">
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
              {hasNext && (
                <button className="load-more dark" onClick={loadMoreEvents} disabled={eventLoading}>
                  {eventLoading ? "正在加载..." : "加载更多"}
                </button>
              )}
            </section>
          </>
        )}
      </section>
    </main>
  );
}

function FilterBar({
  channel,
  filters,
  onChange,
  onRefresh
}: {
  channel: PublicChannel;
  filters: { q: string; category: string; date: string; sourceGroup: string };
  onChange: (filters: Partial<{ category: string; date: string; sourceGroup: string }>) => void;
  onRefresh: () => void;
}) {
  return (
    <section className="aihot-filter-panel">
      <div className="segmented-row" aria-label="信源类型筛选">
        {sourceGroups.map((option) => (
          <button
            key={option.value || "all"}
            className={filters.sourceGroup === option.value ? "active" : ""}
            onClick={() => onChange({ sourceGroup: option.value })}
          >
            {option.label}
          </button>
        ))}
      </div>
      <div className="segmented-row wide" aria-label="分类筛选">
        <button className={!filters.category ? "active" : ""} onClick={() => onChange({ category: "" })}>全部</button>
        {categoryOptions(channel).map((option) => (
          <button
            key={option.value}
            className={filters.category === option.value ? "active" : ""}
            onClick={() => onChange({ category: option.value })}
          >
            {option.shortLabel}
          </button>
        ))}
      </div>
      <label className="date-filter">历史日期
        <input type="date" value={filters.date} onChange={(event) => onChange({ date: event.target.value })} />
      </label>
      <button className="ghost dark" onClick={onRefresh}><RefreshCw size={15} />刷新</button>
    </section>
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
    <section className="public-login-panel dark">
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
  const reason = formatReason(event.entryReason || event.suggestedAction || `来自 ${event.sourceCount} 个来源，系统评分达到精选阈值。`);

  return (
    <article className="aihot-event">
      <div className="timeline-stamp dark">
        {showDate && <span className="timeline-date">{formatMonthDay(event.lastSeenAt)}</span>}
        <strong>{formatTime(event.lastSeenAt)}</strong>
        <i aria-hidden="true" />
      </div>
      <div className="aihot-event-card">
        <div className="event-meta dark">
          <span>{event.mainItem?.sourceName ?? "未知来源"}</span>
          {event.socialHandle && <span>{event.socialHandle}</span>}
          <span>{sourceGroupLabel(event.sourceGroup)}</span>
          <span>{categoryLabel(event.category)}</span>
          <span>{formatDateTime(event.lastSeenAt)}</span>
        </div>
        <div className="event-title-row">
          <h2>{event.title}</h2>
          <strong className="score-badge">精选分 {Math.round(event.score)}</strong>
        </div>
        <p>{summary}</p>
        {event.tags && event.tags.length > 0 && (
          <div className="event-tags dark">
            {event.tags.map((tag) => <span className={tagClass(tag)} key={tag}>{tag}</span>)}
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
          {event.mainItem?.url && <a href={event.mainItem.url} target="_blank" rel="noreferrer"><ExternalLink size={15} />查看原文</a>}
          <button className="ghost dark" onClick={() => { setOpen((current) => !current); if (!open) reload(); }}>
            {open ? "收起详情" : "事件详情"}
          </button>
        </div>
        {open && (
          <div className="public-detail dark">
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

function SourceWall({ api, channel }: { api: PublicApi; channel: PublicChannel }) {
  const { data: sources, error, loading, reload } = useAsyncData<Source[]>(() => api.listSources({ channel }), [], [api, channel]);
  return (
    <section className="source-wall">
      <div className="source-wall-head">
        <div>
          <h2>信源墙</h2>
          <p>每张卡片都是一位贡献者的功劳；审核通过的提报会获得专属编号，永久收录在这里。</p>
        </div>
        <button className="ghost dark" onClick={reload}><RefreshCw size={15} />刷新</button>
      </div>
      {error && <p className="error">{error}</p>}
      {loading && <p className="hint">正在加载信源...</p>}
      <div className="source-wall-grid">
        {sources.map((source) => (
          <article key={source.id} className="source-wall-card">
            <div className="source-card-top">
              <h3>{source.name}</h3>
              <span>{formatContributorNo(source.contributorNo)}</span>
            </div>
            <p>{source.socialHandle ? `${source.socialHandle} · ` : ""}{sourceTypeLabel(source.sourceType)} · {sourceGroupLabel(source.sourceGroup)}</p>
            <div className="source-card-meta">
              <span>{source.tier}</span>
              <span>{collectionStatusLabel(source.collectionStatus)}</span>
              <span>{source.freeAccess ? "免费可读" : "需授权"}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function DailyReader({ api, channel }: { api: PublicApi; channel: PublicChannel }) {
  const [date, setDate] = useState(today());
  const { data: daily, error, loading, reload } = useAsyncData<PublicDaily | null>(() => api.getDaily({ channel, date }), null, [channel, date]);
  const highlights = dailyHighlights(daily);

  return (
    <section className="daily-reader dark">
      <div className="public-filters horizontal dark">
        <label>频道<input value={channels[channel].title} readOnly /></label>
        <label>日期<input type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label>
        <button className="ghost dark" onClick={reload}>刷新日报</button>
      </div>
      {error && <p className="error">{error}</p>}
      {loading && !daily && <p className="hint">正在读取日报...</p>}
      {daily ? (
        <article className="daily-document dark">
          <p className="eyebrow">{channelLabel(daily.channel)} · {daily.date}</p>
          <h2>{daily.title}</h2>
          <p className="hint">{daily.windowLabel || "基于最近 24 小时精选情报自动生成"}</p>
          {highlights.map((item, index) => (
            <section className="daily-timeline-item" key={item.eventId || item.title}>
              <div className="timeline-stamp compact dark">
                {index === 0 && <span className="timeline-date">{formatMonthDay(String(item.lastSeenAt ?? daily.generatedAt))}</span>}
                <strong>{formatTime(String(item.lastSeenAt ?? daily.generatedAt))}</strong>
                <i aria-hidden="true" />
              </div>
              <div>
                <strong>{item.title}</strong>
                <p>{String(item.summary ?? "待 AI 处理后生成中文摘要。")}</p>
                <span>{categoryLabel(String(item.category ?? ""))} · 精选分 {Math.round(Number(item.score ?? 0))}</span>
                <span>{formatReason(String(item.entryReason ?? "待 AI 处理后生成推荐理由。"))}</span>
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
    <section className="rss-grid dark">
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
      { value: "policy", label: "政策监管", shortLabel: "政策" },
      { value: "account_health", label: "账号健康", shortLabel: "账号" },
      { value: "fba_logistics", label: "FBA 物流", shortLabel: "FBA" },
      { value: "ads_ppc", label: "广告投放", shortLabel: "广告" },
      { value: "listing_seo", label: "Listing 与搜索", shortLabel: "Listing" },
      { value: "fees_margin", label: "费用利润", shortLabel: "费用" },
      { value: "product_research", label: "选品研究", shortLabel: "选品" },
      { value: "tools", label: "卖家工具", shortLabel: "工具" },
      { value: "compliance_trade", label: "合规贸易", shortLabel: "合规" }
    ];
  }
  return [
    { value: "ai_models", label: "AI 模型", shortLabel: "模型" },
    { value: "ai_products", label: "AI 产品", shortLabel: "产品" },
    { value: "industry", label: "行业观察", shortLabel: "行业" },
    { value: "papers", label: "论文报告", shortLabel: "论文" },
    { value: "agent_tools", label: "Agent 与工具", shortLabel: "技巧" },
    { value: "monetization", label: "商业变现", shortLabel: "商业化" }
  ];
}

function dailyHighlights(daily: PublicDaily | null) {
  const sections = daily?.sections;
  if (!sections || !Array.isArray(sections.highlights)) return [] as Array<Record<string, string | number | null>>;
  return sections.highlights.filter((item): item is Record<string, string | number | null> => Boolean(item) && typeof item === "object");
}

function sectionTitle(section: PublicSection) {
  return {
    selected: "精选",
    all: "全部热点",
    daily: "AI 日报",
    rss: "RSS 订阅",
    sources: "信源墙"
  }[section];
}

function sectionDescription(section: PublicSection, fallback: string) {
  return {
    selected: "AI 自动挑选的高价值内容",
    all: fallback,
    daily: "基于最近 24 小时精选情报自动生成",
    rss: "把事件流和日报接入你的阅读器",
    sources: "公开展示已收录和待接入的信源贡献"
  }[section];
}

function formatReason(reason: string) {
  return reason.startsWith("推荐理由") ? reason : `推荐理由：${reason}`;
}

function formatContributorNo(value?: string | null) {
  if (!value) return "AIHOT · --";
  const parts = value.split("-");
  if (parts.length === 2) return `${parts[0]} · ${parts[1]}`;
  return value;
}

function tagClass(tag: string) {
  if (/风险|合规|账号|费用/.test(tag)) return "tag-risk";
  if (/行动|广告|Listing|FBA|API/.test(tag)) return "tag-action";
  if (/OpenAI|GPT|Claude|Gemini|Amazon|SP-API/i.test(tag)) return "tag-keyword";
  return "tag-normal";
}
