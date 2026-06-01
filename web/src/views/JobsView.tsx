import { Lock, RotateCcw } from "lucide-react";
import { useState } from "react";
import type { AdminApi } from "../api";
import { AdminChannelCards, usePersistedAdminChannel } from "../components/AdminChannelCards";
import { MetricCard, MetricGrid } from "../components/MetricCard";
import { Section, TableWrap } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { useAsyncData } from "../hooks";
import type { Job } from "../types";
import { formatDateTime } from "../utils";

export function JobsView({ api }: { api: AdminApi }) {
  const [channel, setChannel] = usePersistedAdminChannel("admin-jobs-channel");
  const [status, setStatus] = useState("");
  const [retryState, setRetryState] = useState<{ jobId: string; tone: "info" | "success" | "error"; text: string } | null>(null);
  const { data: jobs, reload, error, loading } = useAsyncData(() => api.listJobs({ channel, status }), [] as Job[], [channel, status]);

  async function retry(job: Job) {
    setRetryState({ jobId: job.id, tone: "info", text: `正在重试任务 ${job.id}...` });
    try {
      await api.retryJob(job.id);
      setRetryState({ jobId: job.id, tone: "success", text: `任务 ${job.id} 已重新入队。` });
      reload();
    } catch (err) {
      setRetryState({ jobId: job.id, tone: "error", text: err instanceof Error ? err.message : "任务重试失败。" });
    }
  }

  const failedJobs = jobs.filter((job) => job.status === "failed" || job.lastError);
  const lockedJobs = jobs.filter(isLockedJob);

  return (
    <div className="view-stack">
      <AdminChannelCards value={channel} onChange={setChannel} metrics={[{ channel, metrics: { sourceCount: jobs.length } }]} />
      <MetricGrid>
        <MetricCard label="待处理" value={jobs.filter((job) => job.status === "pending").length} />
        <MetricCard label="锁定/执行中" value={lockedJobs.length} tone={lockedJobs.length ? "warn" : "neutral"} />
        <MetricCard label="失败任务" value={failedJobs.length} tone={failedJobs.length ? "bad" : "good"} />
      </MetricGrid>
      <Section
        title="任务队列"
        description={loading ? "正在刷新任务状态..." : `当前 ${jobs.length} 个任务，失败和锁定任务优先排查。`}
        error={error}
        action={<select value={status} onChange={(event) => setStatus(event.target.value)} disabled={loading}><option value="">全部状态</option><option value="pending">待处理</option><option value="locked">已领取</option><option value="running">运行中</option><option value="succeeded">成功</option><option value="failed">失败</option></select>}
      >
        {retryState && <p className={`form-message ${retryState.tone}`} role="status">{retryState.text}</p>}
        <TableWrap>
          <table>
            <thead><tr><th>任务</th><th>状态/锁定</th><th>失败原因</th><th>重试入口</th><th>优先级</th><th>尝试</th><th>计划时间</th><th>更新时间</th></tr></thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td>
                    <strong>{job.id}</strong>
                    <span>{job.sourceId}</span>
                  </td>
                  <td>
                    <StatusLabel value={job.status} />
                    {isLockedJob(job) ? (
                      <span><Lock size={12} /> {job.lockedBy || "未知 worker"} · {formatDateTime(job.lockedAt)}</span>
                    ) : (
                      <span>未锁定</span>
                    )}
                  </td>
                  <td>
                    <strong>{failureText(job)}</strong>
                    <span>{job.lastError ? "最近失败原因" : job.status === "failed" ? "等待后台补充错误详情" : "无失败记录"}</span>
                  </td>
                  <td>
                    <button className="ghost" disabled={retryState?.jobId === job.id && retryState.tone === "info"} onClick={() => retry(job)}>
                      <RotateCcw size={15} />
                      {retryState?.jobId === job.id && retryState.tone === "info" ? "重试中..." : "重试"}
                    </button>
                    <span>{retryState?.jobId === job.id ? retryState.text : retryHint(job)}</span>
                  </td>
                  <td>{job.priority}</td>
                  <td>{job.attemptCount}</td>
                  <td>{formatDateTime(job.runAfter)}</td>
                  <td>{formatDateTime(job.updatedAt ?? job.createdAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Section>
    </div>
  );
}

function isLockedJob(job: Job) {
  return job.status === "locked" || job.status === "running" || Boolean(job.lockedAt || job.lockedBy);
}

function failureText(job: Job) {
  if (job.lastError?.trim()) return job.lastError;
  if (job.status === "failed") return "失败但未返回原因";
  return "无";
}

function retryHint(job: Job) {
  if (job.lastError || job.status === "failed") return "失败任务可直接重试";
  if (isLockedJob(job)) return "任务锁定中，确认 worker 状态后重试";
  return "重新排队该抓取任务";
}
