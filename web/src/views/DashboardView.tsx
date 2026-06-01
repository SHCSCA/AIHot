import type { ReactNode } from "react";
import type { AdminApi } from "../api";
import { AdminChannelCards, usePersistedAdminChannel } from "../components/AdminChannelCards";
import { AlertTriangle, CheckCircle2, ClipboardList, Newspaper, RefreshCw, XCircle } from "lucide-react";
import { MetricCard, MetricGrid } from "../components/MetricCard";
import { Section } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { useAsyncData } from "../hooks";
import { categoryLabel, channelLabel } from "../labels";
import type { Dashboard, EventCluster, Job, PipelineRun } from "../types";

const emptyDashboard: Dashboard = {
  metrics: {},
  recentFailedJobs: [],
  pendingReviewEvents: [],
  recentPipelineRuns: []
};

export function DashboardView({ api, initialDashboard }: { api: AdminApi; initialDashboard?: Dashboard | null }) {
  const [channel, setChannel] = usePersistedAdminChannel("admin-dashboard-channel");
  const { data, error, reload } = useAsyncData(() => api.getDashboard({ channel }), initialDashboard ?? emptyDashboard, [
    channel
  ]);
  const metrics = data.metrics;
  const healthWarningCount = Number(metrics.healthWarningCount ?? 0);
  const failedJobCount = Number(metrics.failedJobCount ?? 0);
  const pendingJobCount = Number(metrics.pendingJobCount ?? 0);
  const pendingReviewEventCount = Number(metrics.pendingReviewEventCount ?? 0);
  const publishedDailyCount = Number(metrics.publishedDailyCount ?? 0);
  const failedJobs = data.recentFailedJobs ?? [];
  const pendingEvents = data.pendingReviewEvents ?? [];
  const recentPipelineRuns = data.recentPipelineRuns ?? [];
  const latestRun = recentPipelineRuns[0] ?? null;

  return (
    <div className="view-stack">
      <MetricGrid>
        <MetricCard label="信源总数" value={metrics.sourceCount ?? 0} detail={channelLabel(channel)} />
        <MetricCard label="健康告警" value={healthWarningCount} tone={healthWarningCount > 0 ? "warn" : "good"} detail={healthWarningCount > 0 ? "需排查" : "正常"} />
        <MetricCard label="待处理任务" value={pendingJobCount} detail="抓取队列" />
        <MetricCard label="失败任务" value={failedJobCount} tone={failedJobCount > 0 ? "bad" : "good"} detail={failedJobs.length ? `最近 ${failedJobs.length} 条` : "暂无失败"} />
        <MetricCard label="待审核事件" value={pendingReviewEventCount} tone={pendingReviewEventCount > 0 ? "warn" : "good"} detail={pendingEvents.length ? `面板 ${pendingEvents.length} 条` : "暂无待审"} />
        <MetricCard label="已发布日报" value={publishedDailyCount} tone={publishedDailyCount > 0 ? "good" : "warn"} detail="发布监控" />
      </MetricGrid>
      <AdminChannelCards value={channel} onChange={setChannel} metrics={data.channelMetrics} />

      <Section
        title="运营 Inbox"
        description={`${channelLabel(channel)} 指挥台 · 按处理优先级聚合当前运营信号`}
        error={error}
        className="ops-inbox-section"
        action={<button onClick={reload}><RefreshCw size={15} />刷新</button>}
      >
        <div className="lab-mode-panel ops-inbox-grid" aria-label="运营 Inbox 摘要">
          <InboxSignal
            icon={<AlertTriangle size={18} />}
            label="健康告警"
            value={healthWarningCount}
            tone={healthWarningCount > 0 ? "warn" : "good"}
            detail={healthWarningCount > 0 ? "优先排查异常信源，避免抓取质量继续下降。" : "当前频道暂无健康告警。"}
          />
          <InboxSignal
            icon={<XCircle size={18} />}
            label="失败任务"
            value={failedJobCount}
            tone={failedJobCount > 0 ? "bad" : "good"}
            detail={failedJobCount > 0 ? `${failedJobs.length} 条最近失败记录可扫读。` : "最近任务没有失败记录。"}
          />
          <InboxSignal
            icon={<ClipboardList size={18} />}
            label="待审核事件"
            value={pendingReviewEventCount}
            tone={pendingReviewEventCount > 0 ? "warn" : "good"}
            detail={pendingReviewEventCount > 0 ? "进入审核队列，决定是否公开展示。" : "审核队列已清空。"}
          />
          <InboxSignal
            icon={publishedDailyCount > 0 ? <CheckCircle2 size={18} /> : <Newspaper size={18} />}
            label="日报状态"
            value={publishedDailyCount}
            tone={publishedDailyCount > 0 ? "good" : "warn"}
            detail={dailyStatusText(publishedDailyCount, latestRun)}
          />
        </div>
      </Section>

      <Section
        title="最近失败任务"
        description={failedJobs.length ? "按最近返回的失败任务展示，先看错误摘要和重试次数。" : "当前频道最近没有失败任务。"}
        className="ops-panel-section"
      >
        {failedJobs.length > 0 ? (
          <div className="lab-mode-panel ops-panel-list" aria-label="最近失败任务列表">
            {failedJobs.map((job) => (
              <FailedJobPanel key={job.id} job={job} />
            ))}
          </div>
        ) : (
          <EmptyPanel title="暂无失败任务" detail="抓取队列没有返回失败记录，可以继续关注健康告警和待处理任务。" />
        )}
      </Section>
      <Section
        title="待审核事件"
        description={pendingEvents.length ? "高分事件优先扫读标题、频道、来源数量和审核状态。" : "当前频道没有等待审核的事件。"}
        className="ops-panel-section"
      >
        {pendingEvents.length > 0 ? (
          <div className="lab-mode-panel ops-panel-list" aria-label="待审核事件列表">
            {pendingEvents.map((event) => (
              <PendingEventPanel key={event.id} event={event} />
            ))}
          </div>
        ) : (
          <EmptyPanel title="暂无待审核事件" detail="事件审核队列为空，不显示空表格。" />
        )}
      </Section>
    </div>
  );
}

function InboxSignal({
  icon,
  label,
  value,
  tone,
  detail
}: {
  icon: ReactNode;
  label: string;
  value: number;
  tone: "good" | "warn" | "bad";
  detail: string;
}) {
  return (
    <div className={`ops-inbox-card ops-inbox-card-${tone}`} data-tone={tone}>
      <span className="ops-inbox-card-label">{icon}{label}</span>
      <strong>{value}</strong>
      <code>{detail}</code>
    </div>
  );
}

function FailedJobPanel({ job }: { job: Job }) {
  const timestamp = formatTime(job.updatedAt ?? job.createdAt ?? job.lockedAt ?? job.runAfter);

  return (
    <div className="ops-panel-card ops-panel-card-bad">
      <span>任务 #{job.id}</span>
      <strong>{job.sourceId}</strong>
      <code>{job.lastError || "没有错误详情"}</code>
      <p className="hint">{[
        `重试 ${job.attemptCount} 次`,
        `优先级 ${job.priority}`,
        timestamp ? `更新 ${timestamp}` : null
      ].filter(Boolean).join(" · ")}</p>
      <StatusLabel value={job.status} />
    </div>
  );
}

function PendingEventPanel({ event }: { event: EventCluster }) {
  const lastSeen = formatTime(event.lastSeenAt ?? event.firstSeenAt);

  return (
    <div className="ops-panel-card ops-panel-card-warn">
      <span>{channelLabel(event.channel)} · {categoryLabel(event.category)}</span>
      <strong>{event.title}</strong>
      <code>{[
        `分数 ${formatScore(event.score)}`,
        `${event.sourceCount} 信源`,
        `${event.memberCount} 成员`,
        lastSeen ? `最近 ${lastSeen}` : null
      ].filter(Boolean).join(" · ")}</code>
      <StatusLabel value={event.reviewStatus ?? "pending"} />
    </div>
  );
}

function EmptyPanel({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="ops-empty-panel">
      <strong>{title}</strong>
      <p className="hint">{detail}</p>
    </div>
  );
}

function dailyStatusText(publishedDailyCount: number, latestRun: PipelineRun | null) {
  if (publishedDailyCount <= 0) return "暂无已发布日报记录，需要关注发布链路。";
  if (!latestRun) return "已有发布记录，暂无最近 Pipeline 数据。";
  if (latestRun.failed > 0 || latestRun.status === "failed") {
    return `已有发布记录；最近 Pipeline ${latestRun.failed} 个失败项。`;
  }
  return `已有发布记录；最近 Pipeline ${latestRun.status}。`;
}

function formatScore(score: number) {
  return Number.isInteger(score) ? String(score) : score.toFixed(1);
}

function formatTime(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}
