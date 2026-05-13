import { Play } from "lucide-react";
import { useState } from "react";
import type { AdminApi } from "../api";
import { MetricCard, MetricGrid } from "../components/MetricCard";
import { Section, TableWrap } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { useAsyncData } from "../hooks";
import type { PipelineRun } from "../types";
import { formatDateTime } from "../utils";

export function PipelineRunsView({ api }: { api: AdminApi }) {
  const [limit, setLimit] = useState(10);
  const { data: runs, reload, error } = useAsyncData(() => api.listPipelineRuns(), [] as PipelineRun[]);
  async function trigger() {
    await api.createPipelineRun({ workerId: "manual-worker", limit });
    reload();
  }
  const latest = runs[0];
  return (
    <div className="view-stack">
      <MetricGrid>
        <MetricCard label="最近调度" value={latest?.scheduled ?? 0} />
        <MetricCard label="成功任务" value={latest?.succeeded ?? 0} tone="good" />
        <MetricCard label="失败任务" value={latest?.failed ?? 0} tone={(latest?.failed ?? 0) > 0 ? "bad" : "good"} />
      </MetricGrid>
      <Section title="流水线控制台" description="手动执行一次调度和 worker 闭环。" error={error}>
        <div className="inline-actions"><label>处理上限<input value={limit} onChange={(event) => setLimit(Number(event.target.value))} /></label><button className="primary" onClick={trigger}><Play size={15} />触发流水线</button></div>
      </Section>
      <Section title="运行历史">
        <TableWrap>
          <table>
            <thead><tr><th>ID</th><th>状态</th><th>调度</th><th>领取</th><th>成功</th><th>失败</th><th>原始文档</th><th>事件簇</th><th>开始</th><th>错误</th></tr></thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}><td>{run.id}</td><td><StatusLabel value={run.status} /></td><td>{run.scheduled}</td><td>{run.claimed}</td><td>{run.succeeded}</td><td>{run.failed}</td><td>{run.rawDocumentsInserted}</td><td>{run.clusters}</td><td>{formatDateTime(run.startedAt)}</td><td>{run.errorMessage ?? "无"}</td></tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Section>
    </div>
  );
}
