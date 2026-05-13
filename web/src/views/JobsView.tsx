import { RotateCcw } from "lucide-react";
import { useState } from "react";
import type { AdminApi } from "../api";
import { MetricCard, MetricGrid } from "../components/MetricCard";
import { Section, TableWrap } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { useAsyncData } from "../hooks";
import type { Job } from "../types";
import { formatDateTime } from "../utils";

export function JobsView({ api }: { api: AdminApi }) {
  const [status, setStatus] = useState("");
  const { data: jobs, reload, error } = useAsyncData(() => api.listJobs({ status }), [] as Job[]);
  async function retry(job: Job) {
    await api.retryJob(job.id);
    reload();
  }
  return (
    <div className="view-stack">
      <MetricGrid>
        <MetricCard label="待处理" value={jobs.filter((job) => job.status === "pending").length} />
        <MetricCard label="执行中" value={jobs.filter((job) => ["locked", "running"].includes(job.status)).length} tone="warn" />
        <MetricCard label="失败任务" value={jobs.filter((job) => job.lastError).length} tone="bad" />
      </MetricGrid>
      <Section title="任务队列" error={error} action={<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">全部状态</option><option value="pending">待处理</option><option value="succeeded">成功</option><option value="failed">失败</option></select>}>
        <TableWrap>
          <table>
            <thead><tr><th>ID</th><th>信源</th><th>状态</th><th>优先级</th><th>尝试</th><th>计划时间</th><th>错误</th><th>操作</th></tr></thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td>{job.id}</td><td>{job.sourceId}</td><td><StatusLabel value={job.status} /></td><td>{job.priority}</td><td>{job.attemptCount}</td><td>{formatDateTime(job.runAfter)}</td><td>{job.lastError ?? "无"}</td>
                  <td><button className="ghost" onClick={() => retry(job)}><RotateCcw size={15} />重试</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Section>
    </div>
  );
}
