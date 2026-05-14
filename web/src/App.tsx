import {
  Activity,
  BarChart3,
  CalendarDays,
  ClipboardList,
  Database,
  GitBranch,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Play,
  SlidersHorizontal,
  RadioTower,
  ShieldCheck
} from "lucide-react";
import { useMemo, useState } from "react";
import { AdminApi, PublicApi, type Credentials } from "./api";
import type { Dashboard } from "./types";
import { DailyDigestsView } from "./views/DailyDigestsView";
import { DashboardView } from "./views/DashboardView";
import { EvaluationsView } from "./views/EvaluationsView";
import { EventsReviewView } from "./views/EventsReviewView";
import { FeedbackView } from "./views/FeedbackView";
import { HealthView } from "./views/HealthView";
import { JobsView } from "./views/JobsView";
import { PipelineRunsView } from "./views/PipelineRunsView";
import { PublicFrontPage } from "./views/PublicFrontPage";
import { QualityView } from "./views/QualityView";
import { SourcesView } from "./views/SourcesView";
import { StrategiesView } from "./views/StrategiesView";
import "./styles.css";

export { SourcesView } from "./views/SourcesView";

type View =
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
  | "evaluations";

type ViewMeta = {
  id: View;
  label: string;
  title: string;
  description: string;
  icon: typeof RadioTower;
};

const navItems: ViewMeta[] = [
  { id: "dashboard", label: "工作台", title: "工作台", description: "查看生产运营核心指标、失败任务和待审核事件。", icon: LayoutDashboard },
  { id: "sources", label: "信源管理", title: "信源管理", description: "维护 AI 与 Amazon 情报信源、采集方式、权威等级和启停状态。", icon: RadioTower },
  { id: "health", label: "健康监控", title: "健康监控", description: "跟踪信源健康分、错误次数、重复率、噪声率和下一次抓取。", icon: Activity },
  { id: "quality", label: "质量校准", title: "质量校准", description: "查看最近 24 小时抓取、初筛、精筛、精选和发布漏斗，定位内容质量瓶颈。", icon: SlidersHorizontal },
  { id: "jobs", label: "任务队列", title: "任务队列", description: "查看抓取任务状态、失败原因，并对失败任务发起重试。", icon: ClipboardList },
  { id: "events", label: "事件审核", title: "事件审核", description: "审核事件簇，查看成员来源，并提交人工反馈。", icon: ShieldCheck },
  { id: "daily", label: "日报发布", title: "日报发布", description: "生成、预览、发布和取消发布每日情报摘要。", icon: CalendarDays },
  { id: "pipeline", label: "流水线控制台", title: "流水线控制台", description: "人工触发一次流水线，查看调度、产出和失败统计。", icon: Play },
  { id: "strategies", label: "策略版本", title: "策略版本", description: "创建、查看和激活频道级策略。", icon: GitBranch },
  { id: "feedback", label: "人工反馈", title: "人工反馈", description: "记录误选、漏选、提权和降权反馈，用于后续评估。", icon: MessageSquare },
  { id: "evaluations", label: "评估运行", title: "评估运行", description: "按频道、策略版本和样本窗口执行评估，沉淀可比较的质量指标。", icon: BarChart3 }
];

export function App() {
  const [view, setView] = useState<View>("dashboard");
  const [credentials, setCredentials] = useState<Credentials | null>(() => loadCredentials());
  const [initialDashboard, setInitialDashboard] = useState<Dashboard | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [adminOpen, setAdminOpen] = useState(() => Boolean(loadCredentials()));
  const publicApi = useMemo(() => new PublicApi(), []);

  function logout(message?: string) {
    sessionStorage.removeItem("adminCredentials");
    setInitialDashboard(null);
    setCredentials(null);
    setAdminOpen(false);
    setLoginError(message ?? null);
    window.history.replaceState(null, "", "/");
  }

  const api = useMemo(
    () => (credentials ? new AdminApi(credentials, "", () => logout("登录已失效，请重新登录。")) : null),
    [credentials]
  );
  const activeView = navItems.find((item) => item.id === view) ?? navItems[0];

  async function login(nextCredentials: Credentials) {
    const loginApi = new AdminApi(nextCredentials);
    const dashboard = await loginApi.getDashboard();
    sessionStorage.setItem("adminCredentials", JSON.stringify(nextCredentials));
    setInitialDashboard(dashboard);
    setCredentials(nextCredentials);
    setAdminOpen(true);
    setLoginError(null);
    window.history.replaceState(null, "", "/admin");
  }

  if (!api || !adminOpen) {
    return <PublicFrontPage api={publicApi} loginError={loginError} loginOpen={window.location.pathname.startsWith("/admin")} onLogin={login} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Database size={21} /></div>
          <div><strong>AI 热点情报平台</strong><span>运营控制台</span></div>
        </div>
        <nav aria-label="后台导航">
          {navItems.map((item) => {
            const Icon = item.icon;
            return <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}><Icon size={17} />{item.label}</button>;
          })}
        </nav>
      </aside>
      <main>
        <header className="topbar">
          <div className="title-block">
            <p className="eyebrow">生产运营后台</p>
            <h1>{activeView.title}</h1>
            <p>{activeView.description}</p>
          </div>
          <div className="admin-user">
            <span>当前用户：{credentials?.username}</span>
            <button className="ghost" onClick={() => logout()}><LogOut size={16} />退出登录</button>
          </div>
        </header>
        <section className="workspace">
          {view === "dashboard" && <DashboardView api={api} initialDashboard={initialDashboard} />}
          {view === "sources" && <SourcesView api={api} />}
          {view === "health" && <HealthView api={api} />}
          {view === "quality" && <QualityView api={api} />}
          {view === "jobs" && <JobsView api={api} />}
          {view === "events" && <EventsReviewView api={api} />}
          {view === "daily" && <DailyDigestsView api={api} />}
          {view === "pipeline" && <PipelineRunsView api={api} />}
          {view === "strategies" && <StrategiesView api={api} />}
          {view === "feedback" && <FeedbackView api={api} />}
          {view === "evaluations" && <EvaluationsView api={api} />}
        </section>
      </main>
    </div>
  );
}

function loadCredentials(): Credentials | null {
  const stored = sessionStorage.getItem("adminCredentials");
  if (!stored) return null;
  return JSON.parse(stored) as Credentials;
}
