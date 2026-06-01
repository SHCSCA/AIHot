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
import { PublicFeedback } from "./PublicFeedback";

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
  const [sourceCounts, setSourceCounts] = useState<Partial<Record<PublicChannel, number>>>({});
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
    if (typeof api.listChannels !== "function") return;
    let active = true;
    api.listChannels()
      .then((channels) => {
        if (!active) return;
        const counts: Partial<Record<PublicChannel, number>> = {};
        for (const item of channels) {
          if ((item.id === "ai" || item.id === "amazon") && Number.isFinite(item.sourceCount)) {
            counts[item.id] = item.sourceCount;
          }
        }
        setSourceCounts(counts);
      })
      .catch(() => undefined);
    return () => { active = false; };
  }, [api]);

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
    overview: { title: "总览", desc: channel === "ai" ? "AI 热点情报聚合" : "Amazon 卖家情报聚合" },
    selected: { title: "精选", desc: channel === "ai" ? "AI 自动挑选的高价值内容" : "Amazon 自动挑选的卖家情报" },
    all: { title: "全部热点", desc: channelInfo[channel].description },
    daily: { title: channel === "ai" ? "AI 日报" : "Amazon 日报", desc: "基于最近 24 小时精选情报自动生成" },
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
          <HeroSection channel={channel} sourceCount={sourceCounts[channel]} />
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
