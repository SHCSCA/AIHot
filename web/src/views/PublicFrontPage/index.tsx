import { useEffect, useState } from "react";
import type { Credentials, PublicApi } from "../../api";

import { TopNav } from "./TopNav";
import { HeroSection } from "./HeroSection";
import { FilterBar } from "./FilterBar";
import { EventTimeline } from "./EventTimeline";
import { DailyReader } from "./DailyReader";
import { SourceWall } from "./SourceWall";
import { RssLinks } from "./RssLinks";
import { LoginPanel } from "./LoginPanel";

export type PublicChannel = "ai" | "amazon";
export type PublicSection = "overview" | "selected" | "all" | "daily" | "rss" | "sources" | "feedback";
type ResolvedTheme = "dark" | "light";
type ThemePreference = ResolvedTheme | "system";

export function PublicFrontPage({
  api,
  loginError,
  loginOpen,
  onLogin,
  embedded = false,
  hideLoginControls = false,
  channelValue,
  sectionValue,
  searchValue,
  themeValue,
  onChannelChange,
  onSectionChange,
  onSearchChange,
  onThemeChange
}: {
  api: PublicApi;
  loginError: string | null;
  loginOpen: boolean;
  onLogin: (credentials: Credentials) => Promise<void>;
  embedded?: boolean;
  hideLoginControls?: boolean;
  channelValue?: PublicChannel;
  sectionValue?: PublicSection;
  searchValue?: string;
  themeValue?: ThemePreference;
  onChannelChange?: (channel: PublicChannel) => void;
  onSectionChange?: (section: PublicSection) => void;
  onSearchChange?: (query: string) => void;
  onThemeChange?: (theme: ThemePreference) => void;
}) {
  const [internalChannel, setInternalChannel] = useState<PublicChannel>("ai");
  const [internalSection, setInternalSection] = useState<PublicSection>(() => sectionFromPath(window.location.pathname));
  const [internalTheme, setInternalTheme] = useState<ThemePreference>(() => loadTheme());
  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>(() => getSystemTheme());
  const [showLogin, setShowLogin] = useState(loginOpen);
  const [filters, setFilters] = useState({ q: "", category: "", date: "", sourceGroup: "" });
  const [page, setPage] = useState(1);
  const [eventVersion, setEventVersion] = useState(0);
  const channel = channelValue ?? internalChannel;
  const section = sectionValue ?? internalSection;
  const theme = themeValue ?? internalTheme;
  const activeMode = section === "all" ? "all" : "selected";
  const resolvedTheme = theme === "system" ? systemTheme : theme;

  useEffect(() => {
    if (searchValue === undefined) return;
    setFilters((current) => (current.q === searchValue ? current : { ...current, q: searchValue }));
    setPage(1);
  }, [searchValue]);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const syncSystemTheme = () => setSystemTheme(media.matches ? "dark" : "light");
    syncSystemTheme();
    media.addEventListener?.("change", syncSystemTheme);
    return () => media.removeEventListener?.("change", syncSystemTheme);
  }, []);

  useEffect(() => {
    if (embedded) return;
    document.documentElement.dataset.theme = resolvedTheme;
    localStorage.setItem("publicTheme", theme);
  }, [embedded, resolvedTheme, theme]);

  function switchChannel(next: PublicChannel) {
    setInternalChannel(next);
    onChannelChange?.(next);
    setFilters({ q: "", category: "", date: "", sourceGroup: "" });
    setPage(1);
    setEventVersion((current) => current + 1);
  }

  function switchSection(next: PublicSection) {
    setInternalSection(next);
    onSectionChange?.(next);
    setPage(1);
    window.history.replaceState(null, "", next === "overview" ? "/" : `/${next}`);
  }

  function switchTheme(next: ThemePreference) {
    setInternalTheme(next);
    onThemeChange?.(next);
  }

  const channelInfo = {
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

  const sectionInfo = {
    overview: { title: "总览", desc: "AI 与 Amazon 情报聚合" },
    selected: { title: "精选", desc: "AI 自动挑选的高价值内容" },
    all: { title: "全部热点", desc: channelInfo[channel].description },
    daily: { title: "AI 日报", desc: "基于最近 24 小时精选情报自动生成" },
    rss: { title: "RSS 订阅", desc: "把事件流和日报接入你的阅读器" },
    sources: { title: "信源墙", desc: "公开展示已收录和待接入的信源贡献" },
    feedback: { title: "反馈", desc: "用户提交的质量信号会进入后台评估" }
  };

  const activeChannel = channelInfo[channel];
  const activeSection = sectionInfo[section];
  const activeWindowLabel = channel === "amazon" ? "最近 7 天" : "最近 24 小时";

  return (
    <main className="aihot-public-shell" data-motion="breathing">
      {!embedded && (
        <TopNav
          channel={channel}
          section={section}
          theme={theme}
          filters={filters}
          onChannelChange={switchChannel}
          onSectionChange={switchSection}
          onThemeChange={switchTheme}
          onSearchChange={(q) => {
            setFilters((prev) => ({ ...prev, q }));
            onSearchChange?.(q);
            setPage(1);
          }}
          onLoginClick={() => setShowLogin((prev) => !prev)}
          hideLoginControls={hideLoginControls}
        />
      )}

      <section className={embedded ? "aihot-workspace unified-public-workspace" : "aihot-workspace"}>
        {section !== "daily" && !embedded && (
          <header className="aihot-topbar">
            <div>
              <h1>{activeSection.title}</h1>
              <p>{activeSection.desc} · 当前展示{activeWindowLabel}情报</p>
              <span>{activeChannel.scope}</span>
            </div>
            {!hideLoginControls && (
              <button className="login-trigger dark" onClick={() => setShowLogin((prev) => !prev)}>
                运营登录
              </button>
            )}
          </header>
        )}

        {showLogin && <LoginPanel error={loginError} onLogin={onLogin} />}

        {section === "overview" ? (
          <HeroSection channel={channel} />
        ) : section === "daily" ? (
          <DailyReader api={api} channel={channel} />
        ) : section === "rss" ? (
          <RssLinks channel={channel} />
        ) : section === "sources" ? (
          <SourceWall api={api} channel={channel} q={filters.q} />
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
            <EventTimeline
              api={api}
              channel={channel}
              activeMode={activeMode}
              filters={filters}
              page={page}
              eventVersion={eventVersion}
              onPageChange={setPage}
            />
          </>
        )}
      </section>
    </main>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

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

// ============================================================================
// Utility functions
// ============================================================================

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
  if (pathname.includes("/selected")) return "selected";
  return "overview";
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
