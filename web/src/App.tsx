import {
  Activity,
  ArrowRight,
  BarChart3,
  CalendarDays,
  ClipboardList,
  Database,
  FileClock,
  GitBranch,
  Heart,
  LayoutDashboard,
  List,
  LockKeyhole,
  LogOut,
  MessageSquare,
  Monitor,
  Moon,
  Newspaper,
  Play,
  RadioTower,
  Rss,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Sun,
  UserCog,
  Users,
  Zap
} from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { AdminApi, ApiError, AuthApi, PublicApi, type Credentials } from "./api";
import { AuditLogsView, RolesView, UsersView } from "./views/AdminAccessView";
import type { Dashboard, SessionInfo } from "./types";
import { DailyDigestsView } from "./views/DailyDigestsView";
import { DashboardView } from "./views/DashboardView";
import { EvaluationsView } from "./views/EvaluationsView";
import { EventsReviewView } from "./views/EventsReviewView";
import { FeedbackView } from "./views/FeedbackView";
import { HealthView } from "./views/HealthView";
import { JobsView } from "./views/JobsView";
import { PipelineRunsView } from "./views/PipelineRunsView";
import { PublicFrontPage, type PublicChannel, type PublicSection } from "./views/PublicFrontPage";
import { QualityView } from "./views/QualityView";
import { SourcesView } from "./views/SourcesView";
import { StrategiesView } from "./views/StrategiesView";
import "./styles.css";

export { SourcesView } from "./views/SourcesView";

type ThemePreference = "dark" | "light" | "system";
type AdminView =
  | "dashboard"
  | "sources"
  | "health"
  | "jobs"
  | "quality"
  | "events"
  | "daily"
  | "pipeline"
  | "strategies"
  | "feedback"
  | "evaluations"
  | "users"
  | "roles"
  | "audit"
  | "system";
type ActiveView = `public:${PublicSection}` | `admin:${AdminView}`;
type IconType = typeof Sparkles;

type NavItem = {
  id: ActiveView;
  label: string;
  title: string;
  description: string;
  icon: IconType;
  permission?: string;
};

const guestSession: SessionInfo = {
  user: null,
  roles: ["guest"],
  permissions: ["feedback.create", "public.read"],
  preferences: { theme: "system", defaultChannel: "ai", compactMode: false },
  authenticated: false
};

const publicItems: NavItem[] = [
  { id: "public:selected", label: "精选", title: "精选", description: "自动挑选的高价值情报", icon: Zap },
  { id: "public:all", label: "全部动态", title: "全部动态", description: "AI 与 Amazon 全量情报流", icon: List },
  { id: "public:daily", label: "日报", title: "日报", description: "杂志式每日摘要", icon: Newspaper },
  { id: "public:rss", label: "RSS 订阅", title: "RSS 订阅", description: "订阅事件流和日报", icon: Rss },
  { id: "public:sources", label: "信源墙", title: "信源墙", description: "可信公开信源", icon: RadioTower },
  { id: "public:feedback", label: "反馈", title: "反馈", description: "提交内容质量反馈", icon: MessageSquare }
];

const opsItems: NavItem[] = [
  { id: "admin:dashboard", label: "工作台", title: "工作台", description: "运营总览、失败任务和待审核事件", icon: LayoutDashboard, permission: "ops.dashboard.read" },
  { id: "admin:sources", label: "信源管理", title: "信源管理", description: "维护信源、采集方式和启停状态", icon: RadioTower, permission: "sources.read" },
  { id: "admin:health", label: "健康监控", title: "健康监控", description: "诊断信源健康、错误和抓取质量", icon: Activity, permission: "health.read" },
  { id: "admin:quality", label: "质量校准", title: "质量校准", description: "查看漏斗、拒绝样本和信源贡献", icon: SlidersHorizontal, permission: "quality.read" },
  { id: "admin:jobs", label: "任务队列", title: "任务队列", description: "查看并重试抓取任务", icon: ClipboardList, permission: "jobs.read" },
  { id: "admin:events", label: "事件审核", title: "事件审核", description: "审核事件簇与成员来源", icon: ShieldCheck, permission: "events.read" },
  { id: "admin:daily", label: "日报发布", title: "日报发布", description: "生成、预览和发布日报", icon: CalendarDays, permission: "daily.read" },
  { id: "admin:pipeline", label: "流水线", title: "流水线", description: "查看和触发生产流水线", icon: Play, permission: "ops.dashboard.read" },
  { id: "admin:strategies", label: "策略版本", title: "策略版本", description: "管理频道级筛选和精选策略", icon: GitBranch, permission: "strategies.read" },
  { id: "admin:feedback", label: "人工反馈", title: "人工反馈", description: "处理误选、漏选和提权反馈", icon: Heart, permission: "feedback.read" },
  { id: "admin:evaluations", label: "评估运行", title: "评估运行", description: "执行策略评估并比较结果", icon: BarChart3, permission: "evaluations.read" }
];

const adminItems: NavItem[] = [
  { id: "admin:users", label: "用户管理", title: "用户管理", description: "创建用户、停用账号和分配角色", icon: Users, permission: "users.manage" },
  { id: "admin:roles", label: "角色权限", title: "角色权限", description: "查看和调整角色权限矩阵", icon: UserCog, permission: "roles.manage" },
  { id: "admin:audit", label: "操作审计", title: "操作审计", description: "追踪关键生产操作", icon: FileClock, permission: "system.manage" },
  { id: "admin:system", label: "系统设置", title: "系统设置", description: "系统配置和高风险操作入口", icon: Settings, permission: "system.manage" }
];

export function App() {
  const authApi = useMemo(() => new AuthApi(), []);
  const publicApi = useMemo(() => new PublicApi(), []);
  const [session, setSession] = useState<SessionInfo>(guestSession);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginOpen, setLoginOpen] = useState(() => window.location.pathname.startsWith("/admin"));
  const [activeView, setActiveView] = useState<ActiveView>(() => viewFromPath(window.location.pathname));
  const [channel, setChannel] = useState<PublicChannel>(() => (localStorage.getItem("aihotChannel") === "amazon" ? "amazon" : "ai"));
  const [globalQuery, setGlobalQuery] = useState("");
  const [theme, setTheme] = useState<ThemePreference>(() => loadTheme());
  const [systemTheme, setSystemTheme] = useState<"dark" | "light">(() => getSystemTheme());
  const [initialDashboard, setInitialDashboard] = useState<Dashboard | null>(null);

  const adminApi = useMemo(
    () => new AdminApi("", () => {
      setSession(guestSession);
      setLoginOpen(true);
    }),
    []
  );
  const permissions = useMemo(() => new Set(session.permissions), [session.permissions]);
  const visibleOps = opsItems.filter((item) => !item.permission || permissions.has(item.permission));
  const visibleAdmin = adminItems.filter((item) => !item.permission || permissions.has(item.permission));
  const activeItem = [...publicItems, ...opsItems, ...adminItems].find((item) => item.id === activeView) ?? publicItems[0];
  const isAdminView = activeView.startsWith("admin:");
  const resolvedTheme = theme === "system" ? systemTheme : theme;

  useEffect(() => {
    let active = true;
    authApi.me()
      .then((me) => {
        if (!active) return;
        setSession(me);
        if (me.authenticated && me.preferences?.theme) setTheme(me.preferences.theme);
        if (me.authenticated && (me.preferences?.defaultChannel === "amazon" || me.preferences?.defaultChannel === "ai")) {
          setChannel(me.preferences.defaultChannel);
        }
      })
      .catch(() => {
        if (active) setSession(guestSession);
      })
      .finally(() => {
        if (active) setSessionLoading(false);
      });
    return () => { active = false; };
  }, [authApi]);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const sync = () => setSystemTheme(media.matches ? "dark" : "light");
    sync();
    media.addEventListener?.("change", sync);
    return () => media.removeEventListener?.("change", sync);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme;
    localStorage.setItem("publicTheme", theme);
  }, [resolvedTheme, theme]);

  useEffect(() => {
    localStorage.setItem("aihotChannel", channel);
  }, [channel]);

  async function login(credentials: Credentials) {
    try {
      const next = await authApi.login(credentials);
      setSession(next);
      setLoginError(null);
      setLoginOpen(false);
      if (next.preferences?.theme) setTheme(next.preferences.theme);
      if (window.location.pathname.startsWith("/admin") || activeView.startsWith("admin:")) setActiveView("admin:dashboard");
    } catch (error) {
      setLoginError(formatLoginError(error));
      throw error;
    }
  }

  async function logout() {
    await authApi.logout().catch(() => undefined);
    setSession(guestSession);
    setInitialDashboard(null);
    setActiveView("public:selected");
    window.history.replaceState(null, "", "/");
  }

  function switchTheme(next: ThemePreference) {
    setTheme(next);
    if (session.authenticated) authApi.updatePreferences({ theme: next }).then(setSession).catch(() => undefined);
  }

  function switchChannel(next: PublicChannel) {
    setChannel(next);
    if (session.authenticated) authApi.updatePreferences({ defaultChannel: next }).then(setSession).catch(() => undefined);
  }

  function activate(item: NavItem) {
    setActiveView(item.id);
    if (item.id.startsWith("public:")) {
      const section = item.id.replace("public:", "") as PublicSection;
      window.history.replaceState(null, "", section === "selected" ? "/" : `/${section}`);
    } else {
      window.history.replaceState(null, "", `/admin/${item.id.replace("admin:", "")}`);
    }
  }

  function leaveLoginGate() {
    setLoginOpen(false);
    setLoginError(null);
    if (activeView.startsWith("admin:")) {
      setActiveView("public:selected");
      window.history.replaceState(null, "", "/");
    }
  }

  if (!session.authenticated && (loginOpen || activeView.startsWith("admin:"))) {
    return (
      <AdminLoginGate
        error={loginError}
        loading={sessionLoading}
        onLogin={login}
        onBack={leaveLoginGate}
      />
    );
  }

  return (
    <main className="unified-shell">
      <aside className="unified-sidebar">
        <button className="unified-brand" onClick={() => activate(publicItems[0])} aria-label="AIHOT 首页">
          <span>AI</span><i />HOT
        </button>
        <div className="unified-channel-switch" role="group" aria-label="频道切换">
          <button className={channel === "ai" ? "active" : ""} onClick={() => switchChannel("ai")}><Sparkles size={16} />AI 热点</button>
          <button className={channel === "amazon" ? "active" : ""} onClick={() => switchChannel("amazon")}><Heart size={16} />Amazon</button>
        </div>
        <NavGroup label="公共情报" items={publicItems} activeView={activeView} onActivate={activate} />
        {visibleOps.length > 0 && <NavGroup label="运营能力" items={visibleOps} activeView={activeView} onActivate={activate} />}
        {visibleAdmin.length > 0 && <NavGroup label="系统管理" items={visibleAdmin} activeView={activeView} onActivate={activate} />}
        <div className="unified-sidebar-footer">
          <ThemeToggle value={theme} onChange={switchTheme} />
          {session.authenticated ? (
            <button className="unified-user" onClick={logout}><LogOut size={16} /><span>{session.user?.displayName ?? session.user?.username}</span></button>
          ) : (
            <button className="unified-user" onClick={() => setLoginOpen(true)}><LockKeyhole size={16} /><span>登录账号</span></button>
          )}
        </div>
      </aside>
      <section className="unified-main">
        <header className="unified-topbar">
          <div>
            <p className="eyebrow">{isAdminView ? "运营控制台" : channel === "ai" ? "AI 热点" : "Amazon 情报"}</p>
            <h1>{activeItem.title}</h1>
            <span>{activeItem.description}</span>
          </div>
          <div className="unified-topbar-actions">
            <label className="unified-command">
              <Search size={15} />
              <input
                aria-label="全局搜索"
                value={globalQuery}
                onChange={(event) => setGlobalQuery(event.target.value)}
                placeholder={isAdminView ? "搜索当前运营页面..." : "搜索标题、摘要、信源..."}
              />
            </label>
            {sessionLoading && <span className="session-chip">同步身份...</span>}
            {session.authenticated && <span className="session-chip">{session.roles.join(" / ")}</span>}
            {!session.authenticated && <button className="ghost" onClick={() => setLoginOpen(true)}><LockKeyhole size={16} />运营登录</button>}
          </div>
        </header>
        {loginOpen && !session.authenticated && <UnifiedLoginPanel error={loginError} onLogin={login} onClose={() => setLoginOpen(false)} />}
        <section className="unified-content">
          {renderContent({
            activeView,
            channel,
            publicApi,
            adminApi,
            session,
            globalQuery,
            loginError,
            login,
            setChannel: switchChannel,
            setActiveView,
            initialDashboard,
            setInitialDashboard
          })}
        </section>
      </section>
      <nav className="unified-mobile-nav" aria-label="移动端导航">
        {publicItems.slice(0, 4).map((item) => {
          const Icon = item.icon;
          return <button key={item.id} className={activeView === item.id ? "active" : ""} onClick={() => activate(item)}><Icon size={18} /><span>{item.label}</span></button>;
        })}
        {(visibleOps[0] ?? null) && <button className={activeView.startsWith("admin:") ? "active" : ""} onClick={() => activate(visibleOps[0])}><Database size={18} /><span>工作台</span></button>}
      </nav>
    </main>
  );
}

function AdminLoginGate({
  error,
  loading,
  onLogin,
  onBack
}: {
  error: string | null;
  loading: boolean;
  onLogin: (credentials: Credentials) => Promise<void>;
  onBack: () => void;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setSubmitting(true);
    try {
      await onLogin({ username, password });
    } catch {
      // The gate renders the normalized error from the parent.
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="admin-login-gate">
      <section className="admin-login-hero" aria-label="AIHOT 运营登录">
        <div className="admin-login-symbol" aria-hidden="true"><span /></div>
        <p>AIHOT</p>
        <h1>AIHOT 运营入口</h1>
        <strong>员工与授权运营人员登录入口。</strong>
        <span>普通访客无需登录即可继续浏览公开内容。</span>
      </section>
      <form className="admin-login-card" onSubmit={submit}>
        <div>
          <h2>登录</h2>
          <p>登录后解锁收藏、反馈、信源提报、审核、日报发布和质量校准等内部功能。</p>
        </div>
        <label>
          后台账号
          <input aria-label="管理员账号" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} />
        </label>
        <label>
          后台密码
          <input aria-label="管理员密码" autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        {error && <p className="admin-login-error">{error}</p>}
        {loading && <p className="admin-login-hint">正在同步登录状态...</p>}
        <button className="admin-login-submit" type="submit" disabled={submitting || loading || !username || !password}>
          <span>{submitting ? "正在登录" : "进入运营工作台"}</span><ArrowRight size={17} />
        </button>
        <button className="admin-login-back" type="button" onClick={onBack}>暂不登录，返回 AIHot</button>
      </form>
    </main>
  );
}

function NavGroup({ label, items, activeView, onActivate }: { label: string; items: NavItem[]; activeView: ActiveView; onActivate: (item: NavItem) => void }) {
  return (
    <nav className="unified-nav" aria-label={label}>
      <span>{label}</span>
      {items.map((item) => {
        const Icon = item.icon;
        return <button key={item.id} className={activeView === item.id ? "active" : ""} onClick={() => onActivate(item)}><Icon size={17} />{item.label}</button>;
      })}
    </nav>
  );
}

function ThemeToggle({ value, onChange }: { value: ThemePreference; onChange: (theme: ThemePreference) => void }) {
  return (
    <div className="theme-switcher unified-theme" role="group" aria-label="主题切换" data-active={value}>
      <button className={value === "dark" ? "theme-dot active" : "theme-dot"} aria-label="深色模式" onClick={() => onChange("dark")}><Moon size={15} /></button>
      <button className={value === "system" ? "theme-dot active" : "theme-dot"} aria-label="跟随系统" onClick={() => onChange("system")}><Monitor size={15} /></button>
      <button className={value === "light" ? "theme-dot active" : "theme-dot"} aria-label="浅色模式" onClick={() => onChange("light")}><Sun size={15} /></button>
    </div>
  );
}

function UnifiedLoginPanel({ error, onLogin, onClose }: { error: string | null; onLogin: (credentials: Credentials) => Promise<void>; onClose: () => void }) {
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
    <section className="unified-login-panel">
      <div><ShieldCheck size={20} /><strong>运营身份登录</strong><span>登录后在当前界面解锁运营菜单和操作权限。</span></div>
      <label>管理员账号<input aria-label="管理员账号" value={username} onChange={(event) => setUsername(event.target.value)} /></label>
      <label>管理员密码<input aria-label="管理员密码" type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
      {error && <p className="error">{error}</p>}
      <div className="inline-actions"><button className="primary" onClick={submit} disabled={submitting}>登录</button><button className="ghost" onClick={onClose}>取消</button></div>
    </section>
  );
}

function renderContent({
  activeView,
  channel,
  publicApi,
  adminApi,
  session,
  globalQuery,
  loginError,
  login,
  setChannel,
  setActiveView,
  initialDashboard,
  setInitialDashboard
}: {
  activeView: ActiveView;
  channel: PublicChannel;
  publicApi: PublicApi;
  adminApi: AdminApi;
  session: SessionInfo;
  globalQuery: string;
  loginError: string | null;
  login: (credentials: Credentials) => Promise<void>;
  setChannel: (channel: PublicChannel) => void;
  setActiveView: (view: ActiveView) => void;
  initialDashboard: Dashboard | null;
  setInitialDashboard: (dashboard: Dashboard | null) => void;
}) {
  if (activeView.startsWith("public:")) {
    const section = activeView.replace("public:", "") as PublicSection;
    return (
      <PublicFrontPage
        embedded
        hideLoginControls
        api={publicApi}
        loginError={loginError}
        loginOpen={false}
        onLogin={login}
        channelValue={channel}
        sectionValue={section}
        searchValue={globalQuery}
        onChannelChange={setChannel}
        onSectionChange={(next) => setActiveView(`public:${next}`)}
      />
    );
  }

  const view = activeView.replace("admin:", "") as AdminView;
  const required = [...opsItems, ...adminItems].find((item) => item.id === activeView)?.permission;
  if (!session.authenticated) return <PermissionState title="需要登录" description="登录后可在同一界面解锁运营菜单和管理操作。" />;
  if (required && !session.permissions.includes(required)) return <PermissionState title="无权限" description="当前账号没有访问此功能的权限。" />;

  if (view === "dashboard") return <DashboardView api={adminApi} initialDashboard={initialDashboard} />;
  if (view === "sources") return <SourcesView api={adminApi} />;
  if (view === "health") return <HealthView api={adminApi} />;
  if (view === "quality") return <QualityView api={adminApi} />;
  if (view === "jobs") return <JobsView api={adminApi} />;
  if (view === "events") return <EventsReviewView api={adminApi} />;
  if (view === "daily") return <DailyDigestsView api={adminApi} />;
  if (view === "pipeline") return <PipelineRunsView api={adminApi} />;
  if (view === "strategies") return <StrategiesView api={adminApi} />;
  if (view === "feedback") return <FeedbackView api={adminApi} />;
  if (view === "evaluations") return <EvaluationsView api={adminApi} />;
  if (view === "users") return <UsersView api={adminApi} />;
  if (view === "roles") return <RolesView api={adminApi} />;
  if (view === "audit") return <AuditLogsView api={adminApi} />;
  if (view === "system") return <PermissionState title="系统设置" description="系统配置入口已纳入管理员菜单，具体高风险配置将在后续版本接入。" />;
  setInitialDashboard(null);
  return null;
}

function PermissionState({ title, description }: { title: string; description: string }) {
  return (
    <section className="permission-state">
      <ShieldCheck size={28} />
      <h2>{title}</h2>
      <p>{description}</p>
    </section>
  );
}

function formatLoginError(error: unknown): string {
  if (error instanceof ApiError && error.status === 401) return "账号或密码不正确，请检查后台账号后再试。";
  if (error instanceof ApiError && error.status === 403) return "当前账号没有进入后台的权限。";
  if (error instanceof Error) return error.message;
  return "登录失败，请稍后重试。";
}

function viewFromPath(pathname: string): ActiveView {
  if (pathname.startsWith("/admin/")) {
    const view = pathname.split("/")[2] as AdminView | undefined;
    if (view && ["dashboard", "sources", "health", "jobs", "quality", "events", "daily", "pipeline", "strategies", "feedback", "evaluations", "users", "roles", "audit", "system"].includes(view)) {
      return `admin:${view}`;
    }
    return "admin:dashboard";
  }
  if (pathname.startsWith("/admin")) return "admin:dashboard";
  if (pathname.includes("/daily")) return "public:daily";
  if (pathname.includes("/rss")) return "public:rss";
  if (pathname.includes("/sources")) return "public:sources";
  if (pathname.includes("/feedback")) return "public:feedback";
  if (pathname.includes("/all")) return "public:all";
  return "public:selected";
}

function loadTheme(): ThemePreference {
  const stored = localStorage.getItem("publicTheme");
  return stored === "dark" || stored === "light" || stored === "system" ? stored : "dark";
}

function getSystemTheme(): "dark" | "light" {
  if (typeof window.matchMedia !== "function") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
