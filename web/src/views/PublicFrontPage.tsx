import {
  ExternalLink,
  Heart,
  List,
  LockKeyhole,
  MessageCircle,
  Monitor,
  Moon,
  Newspaper,
  Plus,
  RefreshCw,
  Rss,
  Search,
  ShieldCheck,
  Sparkles,
  Sun,
  Zap
} from "lucide-react";
import { useEffect, useState } from "react";
import type { Credentials, PublicApi } from "../api";
import { PaginationBar } from "../components/PaginationBar";
import {
  categoryLabel,
  channelLabel,
  collectionStatusLabel,
  sellerActionLevelLabel,
  sourceGroupLabel,
  sourceTypeLabel
} from "../labels";
import type { DailyArchiveItem, DailySection, PublicDaily, PublicEvent, PublicEventDetail, PublicFeedLink, Source } from "../types";
import { formatDateTime, formatMonthDay, formatTime, today } from "../utils";
import { useAsyncData } from "../hooks";

type PublicChannel = "ai" | "amazon";
type PublicSection = "selected" | "all" | "daily" | "rss" | "sources" | "feedback";
type ResolvedTheme = "dark" | "light";
type ThemePreference = ResolvedTheme | "system";

const EVENT_PAGE_SIZE = 20;
const SOURCE_PAGE_SIZE = 24;

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
  { id: "sources", label: "信源墙", Icon: Plus },
  { id: "feedback", label: "反馈", Icon: MessageCircle }
];

const sourceGroups = [
  { value: "", label: "全部信源" },
  { value: "official,first_party", label: "官方/一手" },
  { value: "media", label: "资讯" },
  { value: "social,community", label: "社媒/社区" }
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
  const [section, setSection] = useState<PublicSection>(() => sectionFromPath(window.location.pathname));
  const [theme, setTheme] = useState<ThemePreference>(() => loadTheme());
  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>(() => getSystemTheme());
  const [showLogin, setShowLogin] = useState(loginOpen);
  const [filters, setFilters] = useState({ q: "", category: "", date: "", sourceGroup: "" });
  const [events, setEvents] = useState<PublicEvent[]>([]);
  const [eventError, setEventError] = useState<string | null>(null);
  const [eventLoading, setEventLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageInfo, setPageInfo] = useState({ totalPages: 1, total: 0 });
  const [eventVersion, setEventVersion] = useState(0);
  const activeMode = section === "all" ? "all" : "selected";
  const activeChannel = channels[channel];
  const resolvedTheme = theme === "system" ? systemTheme : theme;

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const syncSystemTheme = () => setSystemTheme(media.matches ? "dark" : "light");
    syncSystemTheme();
    media.addEventListener?.("change", syncSystemTheme);
    return () => media.removeEventListener?.("change", syncSystemTheme);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme;
    localStorage.setItem("publicTheme", theme);
  }, [resolvedTheme, theme]);

  useEffect(() => {
    if (section === "daily" || section === "rss" || section === "sources" || section === "feedback") return;
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
        page,
        pageSize: EVENT_PAGE_SIZE
      })
      .then((page) => {
        if (!active) return;
        setEvents(page.items);
        const resolvedPage = page.page ?? 1;
        setPageInfo({
          totalPages: page.totalPages ?? (page.hasNext ? resolvedPage + 1 : resolvedPage),
          total: page.total ?? page.count
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
  }, [
    api,
    channel,
    section,
    activeMode,
    filters.q,
    filters.category,
    filters.date,
    filters.sourceGroup,
    page,
    eventVersion
  ]);

  function switchChannel(next: PublicChannel) {
    setChannel(next);
    setFilters({ q: "", category: "", date: "", sourceGroup: "" });
    setPage(1);
    setEventVersion((current) => current + 1);
  }

  function switchSection(next: PublicSection) {
    setSection(next);
    setPage(1);
    window.history.replaceState(null, "", next === "selected" ? "/" : `/${next}`);
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
            <button key={id} className={section === id ? "active" : ""} onClick={() => switchSection(id)}>
              <Icon size={19} />{label}
            </button>
          ))}
        </nav>
        <div className="aihot-sidebar-bottom">
          <div className="theme-switcher" role="group" aria-label="主题切换" data-active={theme}>
            <button
              type="button"
              className={theme === "dark" ? "theme-dot active" : "theme-dot"}
              aria-label="深色模式"
              onClick={() => setTheme("dark")}
            >
              <Moon size={16} />
            </button>
            <button
              type="button"
              className={theme === "system" ? "theme-dot active" : "theme-dot"}
              aria-label="跟随系统"
              onClick={() => setTheme("system")}
            >
              <Monitor size={16} />
            </button>
            <button
              type="button"
              className={theme === "light" ? "theme-dot active" : "theme-dot"}
              aria-label="浅色模式"
              onClick={() => setTheme("light")}
            >
              <Sun size={16} />
            </button>
          </div>
          <button type="button" className="login-link" onClick={() => setShowLogin((current) => !current)}>
            <LockKeyhole size={16} />后台入口
          </button>
        </div>
      </aside>

      <section className="aihot-workspace">
        {section !== "daily" && (
          <header className="aihot-topbar">
            <div>
              <h1>{section === "selected" ? activeChannel.title : section === "all" ? activeChannel.heading : sectionTitle(section)}</h1>
              <p>{sectionDescription(section, activeChannel.description)} · 当前展示最近 24 小时情报</p>
              <span>{activeChannel.scope}</span>
            </div>
            <div className="aihot-search">
              <Search size={16} />
              <input
                value={filters.q}
                onChange={(event) => {
                  setFilters({ ...filters, q: event.target.value });
                  setPage(1);
                }}
                placeholder="搜索标题/摘要..."
              />
              <button onClick={() => { setPage(1); setEventVersion((current) => current + 1); }}>搜索</button>
            </div>
            <button className="login-trigger dark" onClick={() => setShowLogin((current) => !current)}>
              <LockKeyhole size={16} />运营登录
            </button>
          </header>
        )}

        {showLogin && <PublicLoginPanel error={loginError} onLogin={onLogin} />}

        {section === "daily" ? (
          <DailyReader api={api} channel={channel} />
        ) : section === "rss" ? (
          <RssLinks channel={channel} />
        ) : section === "sources" ? (
          <SourceWall api={api} channel={channel} />
        ) : section === "feedback" ? (
          <PublicFeedback api={api} channel={channel} />
        ) : (
          <>
            <FilterBar
              channel={channel}
              filters={filters}
              onChange={(next) => { setPage(1); setFilters({ ...filters, ...next }); }}
              onRefresh={() => { setPage(1); setEventVersion((current) => current + 1); }}
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
              <PaginationBar
                page={page}
                totalPages={pageInfo.totalPages}
                onPageChange={setPage}
                disabled={eventLoading}
              />
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
  const categories = categoryOptions(channel);
  return (
    <section className="aihot-filter-panel">
      <div className="segmented-row source-tabs" aria-label="信源类型筛选">
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
      <label className="filter-select">分类
        <select aria-label="分类筛选" value={filters.category} onChange={(event) => onChange({ category: event.target.value })}>
          <option value="">全部分类</option>
          {categories.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </label>
      <label className="filter-select date-filter">历史日期
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
        {event.mainItem?.imageUrl && (
          <figure className="event-media event-media-natural">
            <img src={event.mainItem.imageUrl} alt={event.mainItem.imageAlt || event.title} loading="lazy" />
          </figure>
        )}
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
  const [page, setPage] = useState(1);
  const { data: sourcePage, error, loading, reload } = useAsyncData(
    async () => {
      if (typeof api.listSourcesPage === "function") {
        return api.listSourcesPage({ channel, page, pageSize: SOURCE_PAGE_SIZE });
      }
      const sources = await api.listSources({ channel });
      return {
        items: sources,
        count: sources.length,
        page: 1,
        pageSize: SOURCE_PAGE_SIZE,
        total: sources.length,
        totalPages: 1,
        hasNext: false,
        nextCursor: null
      };
    },
    { items: [] as Source[], count: 0, page: 1, pageSize: SOURCE_PAGE_SIZE, total: 0, totalPages: 1, hasNext: false, nextCursor: null },
    [api, channel, page]
  );
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
        {sourcePage.items.map((source) => (
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
      <PaginationBar
        page={page}
        totalPages={sourcePage.totalPages ?? 1}
        onPageChange={setPage}
        disabled={loading}
      />
    </section>
  );
}

function PublicFeedback({ api, channel }: { api: PublicApi; channel: PublicChannel }) {
  const [reason, setReason] = useState("");
  const [contact, setContact] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function submit() {
    if (reason.trim().length < 2) {
      setMessage("请补充具体反馈内容。");
      return;
    }
    setSubmitting(true);
    try {
      await api.submitFeedback({
        channel,
        feedbackType: "general",
        contact: contact.trim() || undefined,
        reason: reason.trim()
      });
      setReason("");
      setContact("");
      setMessage("反馈已提交，后台会把它作为质量评估样本。");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "反馈提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="public-feedback dark">
      <div>
        <p className="eyebrow">反馈</p>
        <h2>说说你的想法</h2>
        <p>发现 bug、想要的功能、看不顺眼的地方都可以告诉我。你的反馈会进入后台质量评估，不会直接改动线上评分。</p>
      </div>
      <div className="feedback-form">
        <label className="feedback-reason">想说点什么？
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="比如：某类内容不够准、日报结构想调整、页面哪里不顺手。"
            maxLength={2000}
          />
        </label>
        <label>联系方式（选填）
          <input value={contact} onChange={(event) => setContact(event.target.value)} placeholder="邮箱 / 微信 / 手机号，任意能联系到你的方式" />
        </label>
        {message && <p className={message.includes("已提交") ? "success" : "error"}>{message}</p>}
        <button className="primary" onClick={submit} disabled={submitting}>
          {submitting ? "提交中..." : "发送反馈"}
        </button>
      </div>
    </section>
  );
}

function DailyReader({ api, channel }: { api: PublicApi; channel: PublicChannel }) {
  const [date, setDate] = useState(today());
  const { data: daily, error, loading, reload } = useAsyncData<PublicDaily | null>(() => api.getDaily({ channel, date }), null, [channel, date]);
  const { data: archive } = useAsyncData(
    () => api.listDailies({ channel, page: 1, pageSize: 20 }),
    { items: [] as DailyArchiveItem[], count: 0, page: 1, pageSize: 20, total: 0, totalPages: 1, hasNext: false, nextCursor: null },
    [api, channel]
  );
  const sections = dailySections(daily);
  const storyCount = daily?.stats?.storyCount ?? sections.reduce((sum, section) => sum + section.items.length, 0);
  const archiveBaseDate = archive.items[0]?.date ?? date;

  return (
    <section className="daily-reader dark">
      <aside className="daily-archive">
        <button className="latest" onClick={() => setDate(today())}>
          <strong>最新一期</strong><span>{today()}</span>
        </button>
        <div className="daily-archive-month">
          <span>{archiveMonthLabel(archiveBaseDate)}</span>
          <em>{archive.items.length}</em>
        </div>
        <div className="daily-archive-list">
          {archive.items.map((item) => (
            <button key={item.id} className={date === item.date ? "active" : ""} onClick={() => setDate(item.date)}>
              <strong>{item.date.slice(8)} 日</strong>
              <span>{item.leadTitle || item.title}</span>
            </button>
          ))}
        </div>
      </aside>
      {error && <p className="error">{error}</p>}
      {loading && !daily && <p className="hint">正在读取日报...</p>}
      {daily ? (
        <article className="daily-document dark">
          <header className="daily-cover">
            <p className="daily-volume">VOL.{daily.date.replaceAll("-", ".")} · {storyCount} STORIES · {channelLabel(daily.channel)} DAILY</p>
            <h2>
              <span className="daily-logo-ai">AI</span>
              <span className="daily-logo-hot">HOT</span>
              <span className="daily-logo-title">日报</span>
            </h2>
            <div className="daily-cover-meta">
              <strong>{dailyDateLabel(daily.date)}</strong>
              <i aria-hidden="true" />
              <span>DAILY · 每早八时</span>
              <button className="ghost dark" onClick={reload}>刷新日报</button>
            </div>
            <p className="daily-cover-summary">{daily.windowLabel || "基于最近 24 小时精选情报自动生成"}</p>
          </header>
          {sections.length > 0 && (
            <nav className="daily-toc" aria-label="日报目录">
              <strong>目录</strong>
              {sections.map((section, sectionIndex) => (
                <a key={section.category} href={`#daily-${section.category}`}>
                  {String(sectionIndex + 1).padStart(2, "0")} {section.label}<span>{section.count} 篇</span>
                </a>
              ))}
            </nav>
          )}
          {sections.length === 0 && <p className="hint">最近 24 小时暂无可发布精选情报。</p>}
          {sections.map((section, sectionIndex) => (
            <section className="daily-section" key={section.category} id={`daily-${section.category}`}>
              <div className="daily-section-title">
                <strong>{String(sectionIndex + 1).padStart(2, "0")}</strong>
                <div>
                  <h3>{section.label}</h3>
                  <span>{sectionEnglishLabel(section.category)}</span>
                </div>
                <em>{section.count} 篇</em>
              </div>
              {section.items.map((item) => (
                <article className="daily-story" key={item.eventId || item.title}>
                  <div className="daily-story-head">
                    <h4>{item.title}</h4>
                    {item.mainItem?.url && <a href={item.mainItem.url} target="_blank" rel="noreferrer"><ExternalLink size={15} />原文</a>}
                  </div>
                  <div className="daily-story-meta">
                    <span>{categoryLabel(item.category)}</span>
                    {item.mainItem?.sourceName && <span>{item.mainItem.sourceName}</span>}
                    <span>精选分 {Math.round(Number(item.score ?? 0))}</span>
                  </div>
                  <p>{item.summary || "待 AI 处理后生成中文摘要。"}</p>
                  {item.entryReason && <em>{formatReason(item.entryReason)}</em>}
                </article>
              ))}
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
      { value: "policy,account_health,compliance_trade", label: "政策账号合规", shortLabel: "政策/账号" },
      { value: "fba_logistics", label: "FBA 与物流", shortLabel: "FBA/物流" },
      { value: "ads_ppc,listing_seo", label: "广告与 Listing", shortLabel: "广告/Listing" },
      { value: "fees_margin,product_research", label: "费用与选品", shortLabel: "费用/选品" },
      { value: "tools", label: "卖家工具", shortLabel: "工具" }
    ];
  }
  return [
    { value: "ai_models,papers", label: "模型与论文", shortLabel: "模型/论文" },
    { value: "ai_products,agent_tools", label: "产品与 Agent", shortLabel: "产品/Agent" },
    { value: "industry,monetization", label: "行业与商业化", shortLabel: "行业/商业化" }
  ];
}

function dailyDateLabel(value: string) {
  const { year, month, day, date } = dateParts(value);
  const weekday = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"][date.getDay()];
  return `${year}年${month}月${day}日　${weekday}`;
}

function archiveMonthLabel(value: string) {
  const { year, month } = dateParts(value);
  return `${year} 年 ${month} 月`;
}

function dateParts(value: string) {
  const [year = 0, month = 1, day = 1] = value.split("-").map((part) => Number(part));
  return { year, month, day, date: new Date(year, month - 1, day) };
}

function sectionEnglishLabel(category: string) {
  if (/ai_models|papers/.test(category)) return "MODEL RELEASES";
  if (/ai_products|agent_tools/.test(category)) return "PRODUCT & AGENTS";
  if (/industry|monetization/.test(category)) return "INDUSTRY SIGNALS";
  if (/policy|account|compliance/.test(category)) return "POLICY & ACCOUNT";
  if (/fba|logistics/.test(category)) return "FBA & LOGISTICS";
  if (/ads|listing/.test(category)) return "ADS & LISTING";
  if (/fees|product/.test(category)) return "MARGIN & SELECTION";
  return "DAILY BRIEF";
}

function dailySections(daily: PublicDaily | null): DailySection[] {
  if (!daily) return [];
  if (Array.isArray(daily.sections)) return daily.sections;
  const legacySections = daily.sectionsJson ?? daily.sections;
  const highlights = Array.isArray(legacySections?.highlights) ? legacySections.highlights : [];
  const items = highlights.filter((item): item is Record<string, string | number | null> => Boolean(item) && typeof item === "object");
  const grouped = new Map<string, DailySection>();
  items.forEach((item) => {
    const category = String(item.category || "industry");
    const section = grouped.get(category) ?? { category, label: categoryLabel(category), count: 0, items: [] };
    section.items.push({
      eventId: item.eventId ? String(item.eventId) : null,
      title: String(item.title || ""),
      summary: item.summary ? String(item.summary) : null,
      entryReason: item.entryReason ? String(item.entryReason) : null,
      category,
      score: Number(item.score || 0),
      lastSeenAt: item.lastSeenAt ? String(item.lastSeenAt) : null
    });
    section.count = section.items.length;
    grouped.set(category, section);
  });
  return [...grouped.values()];
}

function sectionTitle(section: PublicSection) {
  return {
    selected: "精选",
    all: "全部热点",
    daily: "AI 日报",
    rss: "RSS 订阅",
    sources: "信源墙",
    feedback: "反馈"
  }[section];
}

function sectionDescription(section: PublicSection, fallback: string) {
  return {
    selected: "AI 自动挑选的高价值内容",
    all: fallback,
    daily: "基于最近 24 小时精选情报自动生成",
    rss: "把事件流和日报接入你的阅读器",
    sources: "公开展示已收录和待接入的信源贡献",
    feedback: "用户提交的质量信号会进入后台评估"
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

function sectionFromPath(pathname: string): PublicSection {
  if (pathname.includes("/daily")) return "daily";
  if (pathname.includes("/rss")) return "rss";
  if (pathname.includes("/sources")) return "sources";
  if (pathname.includes("/feedback")) return "feedback";
  if (pathname.includes("/all")) return "all";
  return "selected";
}

function loadTheme(): ThemePreference {
  const stored = localStorage.getItem("publicTheme");
  if (stored === "system") return "system";
  return stored === "light" ? "light" : "dark";
}

function getSystemTheme(): ResolvedTheme {
  if (typeof window.matchMedia !== "function") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
