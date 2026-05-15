import type { AdminApi } from "../api";
import { AdminChannelCards, usePersistedAdminChannel } from "../components/AdminChannelCards";
import { MetricCard, MetricGrid } from "../components/MetricCard";
import { Section, TableWrap } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { useAsyncData } from "../hooks";
import type { Dashboard } from "../types";

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
  return (
    <div className="view-stack">
      <MetricGrid>
        <MetricCard label="信源总数" value={metrics.sourceCount ?? 0} />
        <MetricCard label="健康告警" value={metrics.healthWarningCount ?? 0} tone={(metrics.healthWarningCount ?? 0) > 0 ? "warn" : "good"} />
        <MetricCard label="待处理任务" value={metrics.pendingJobCount ?? 0} />
        <MetricCard label="失败任务" value={metrics.failedJobCount ?? 0} tone={(metrics.failedJobCount ?? 0) > 0 ? "bad" : "good"} />
        <MetricCard label="待审核事件" value={metrics.pendingReviewEventCount ?? 0} tone="warn" />
        <MetricCard label="已发布日报" value={metrics.publishedDailyCount ?? 0} tone="good" />
      </MetricGrid>
      <AdminChannelCards value={channel} onChange={setChannel} metrics={data.channelMetrics} />
      <Section title="最近失败任务" error={error} action={<button onClick={reload}>刷新</button>}>
        <TableWrap>
          <table>
            <thead><tr><th>ID</th><th>信源</th><th>状态</th><th>错误</th></tr></thead>
            <tbody>
              {data.recentFailedJobs.map((job) => (
                <tr key={job.id}><td>{job.id}</td><td>{job.sourceId}</td><td><StatusLabel value={job.status} /></td><td>{job.lastError ?? "无"}</td></tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Section>
      <Section title="待审核事件">
        <TableWrap>
          <table>
            <thead><tr><th>事件</th><th>频道</th><th>分数</th><th>状态</th></tr></thead>
            <tbody>
              {data.pendingReviewEvents.map((event) => (
                <tr key={event.id}><td>{event.title}</td><td>{event.channel}</td><td>{event.score}</td><td><StatusLabel value={event.reviewStatus ?? "pending"} /></td></tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Section>
    </div>
  );
}
