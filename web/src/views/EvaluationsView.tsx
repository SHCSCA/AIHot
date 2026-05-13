import { useState } from "react";
import type { AdminApi } from "../api";
import { MetricCard, MetricGrid } from "../components/MetricCard";
import { Section, TableWrap } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { useAsyncData } from "../hooks";
import type { EvaluationRun } from "../types";
import { channelLabel, formatDateTime, jsonLabel } from "../utils";

export function EvaluationsView({ api }: { api: AdminApi }) {
  const [form, setForm] = useState({ channel: "ai", strategyVersion: "ai-default-v1", windowHours: "24" });
  const { data: runs, reload, error } = useAsyncData(() => api.listEvaluationRuns({ channel: form.channel }), [] as EvaluationRun[]);
  const latest = runs[0];
  const labels = latest?.metrics.labels ?? {};
  const values = latest?.metrics.values ?? {};
  async function createRun() {
    await api.createEvaluationRun({ channel: form.channel, strategyVersion: form.strategyVersion, name: `${channelLabel(form.channel)} 策略评估`, request: { windowHours: Number(form.windowHours) } });
    reload();
  }
  async function runEvaluation(run: EvaluationRun) {
    await api.runEvaluationRun(run.id);
    reload();
  }
  return (
    <div className="view-stack">
      <MetricGrid>
        <MetricCard label={labels.selectedEventCount ?? "精选事件数"} value={String(values.selectedEventCount ?? 0)} />
        <MetricCard label={labels.feedbackCount ?? "反馈总数"} value={String(values.feedbackCount ?? 0)} />
        <MetricCard label={labels.falsePositiveCount ?? "误选反馈数"} value={String(values.falsePositiveCount ?? 0)} tone="warn" />
      </MetricGrid>
      <Section title="创建评估运行" error={error}>
        <div className="form-grid">
          <label>频道<select value={form.channel} onChange={(event) => setForm({ ...form, channel: event.target.value })}><option value="ai">AI 热点</option><option value="amazon">Amazon 情报</option></select></label>
          <label>策略版本<input value={form.strategyVersion} onChange={(event) => setForm({ ...form, strategyVersion: event.target.value })} /></label>
          <label>样本窗口（小时）<input value={form.windowHours} onChange={(event) => setForm({ ...form, windowHours: event.target.value })} /></label>
        </div>
        <button className="primary" onClick={createRun}>新建评估</button>
      </Section>
      <Section title="评估历史">
        <TableWrap>
          <table>
            <thead><tr><th>ID</th><th>频道</th><th>策略</th><th>状态</th><th>指标</th><th>完成时间</th><th>操作</th></tr></thead>
            <tbody>{runs.map((run) => <tr key={run.id}><td>{run.id}</td><td>{channelLabel(run.channel)}</td><td>{run.strategyVersion}</td><td><StatusLabel value={run.status} /></td><td><code>{jsonLabel(run.metrics.values)}</code></td><td>{formatDateTime(run.completedAt)}</td><td><button className="primary" onClick={() => runEvaluation(run)}>运行</button></td></tr>)}</tbody>
          </table>
        </TableWrap>
      </Section>
    </div>
  );
}
