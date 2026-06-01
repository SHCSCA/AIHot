import { useState } from "react";
import type { AdminApi } from "../api";
import { AdminChannelCards, usePersistedAdminChannel } from "../components/AdminChannelCards";
import { MetricCard, MetricGrid } from "../components/MetricCard";
import { Section, TableWrap } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { useAsyncData } from "../hooks";
import type { EvaluationRun } from "../types";
import { channelLabel, feedbackLabel, formatDateTime, jsonLabel } from "../utils";

export function EvaluationsView({ api }: { api: AdminApi }) {
  const [channel, setChannel] = usePersistedAdminChannel("admin-evaluations-channel");
  const [form, setForm] = useState({ strategyVersion: "ai-default-v1", windowHours: "24" });
  const { data: runs, reload, error } = useAsyncData(() => api.listEvaluationRuns({ channel }), [] as EvaluationRun[], [channel]);
  const latest = runs[0];
  const labels = latest?.metrics.labels ?? {};
  const values = latest?.metrics.values ?? {};
  const completedCount = runs.filter((run) => run.status === "completed" || run.status === "succeeded").length;
  const feedbackTotal = values.feedbackCount ?? 0;
  const falsePositive = values.falsePositiveCount ?? 0;
  const falseNegative = values.falseNegativeCount ?? 0;
  const sourceContribution = values.sourceContribution;
  async function createRun() {
    await api.createEvaluationRun({ channel, strategyVersion: form.strategyVersion, name: `${channelLabel(channel)} 策略评估`, request: { windowHours: Number(form.windowHours) } });
    reload();
  }
  async function runEvaluation(run: EvaluationRun) {
    await api.runEvaluationRun(run.id);
    reload();
  }
  return (
    <div className="view-stack">
      <AdminChannelCards value={channel} onChange={setChannel} metrics={[{ channel, metrics: { sourceCount: runs.length } }]} />
      <MetricGrid>
        <MetricCard label="最近运行状态" value={latest ? <StatusLabel value={latest.status} /> : "无运行"} tone={latest?.status === "failed" ? "bad" : "neutral"} />
        <MetricCard label={labels.selectedEventCount ?? "精选事件数"} value={metricText(values.selectedEventCount)} />
        <MetricCard label={labels.feedbackCount ?? "反馈总数"} value={metricText(feedbackTotal)} />
        <MetricCard label="已完成运行" value={completedCount} />
      </MetricGrid>
      <Section
        title="Lab Mode · 评估运行"
        description="复用现有评估运行能力，按样本窗口统计精选、反馈和来源贡献，用于策略校准；这里不承诺完整历史回测引擎。"
        error={error}
      >
        <div className="lab-mode-panel" aria-label="最近评估概览">
          <div>
            <span>运行</span>
            <strong>{latest?.name ?? "暂无评估运行"}</strong>
            <code>{latest?.id ?? "未创建"}</code>
          </div>
          <div>
            <span>策略版本</span>
            <strong>{latest?.strategyVersion ?? form.strategyVersion}</strong>
          </div>
          <div>
            <span>反馈分布</span>
            <strong>{feedbackLabel("false_positive")} {metricText(falsePositive)} · {feedbackLabel("false_negative")} {metricText(falseNegative)}</strong>
          </div>
          <div>
            <span>来源贡献</span>
            <strong>{jsonLabel(sourceContribution)}</strong>
          </div>
        </div>
        <div className="form-grid">
          <label>策略版本<input value={form.strategyVersion} onChange={(event) => setForm({ ...form, strategyVersion: event.target.value })} /></label>
          <label>样本窗口（小时）<input value={form.windowHours} onChange={(event) => setForm({ ...form, windowHours: event.target.value })} /></label>
        </div>
        <button className="primary" onClick={createRun}>新建评估</button>
      </Section>
      <Section title="评估历史" description="运行结果来自现有评估指标，适合比较最近窗口的策略表现和人工反馈信号。">
        <TableWrap>
          <table>
            <thead><tr><th>运行</th><th>频道</th><th>策略</th><th>状态</th><th>指标</th><th>反馈分布</th><th>来源贡献</th><th>完成时间</th><th>操作</th></tr></thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td><strong>{run.name}</strong><span>{run.id}</span></td>
                  <td>{channelLabel(run.channel)}</td>
                  <td>{run.strategyVersion}</td>
                  <td><StatusLabel value={run.status} /></td>
                  <td><code>{jsonLabel(run.metrics.values)}</code></td>
                  <td>{feedbackDistributionLabel(run)}</td>
                  <td><code>{jsonLabel(run.metrics.values?.sourceContribution)}</code></td>
                  <td>{formatDateTime(run.completedAt)}</td>
                  <td><button className="primary" onClick={() => runEvaluation(run)}>运行</button></td>
                </tr>
              ))}
              {runs.length === 0 && <tr><td colSpan={9}>当前频道暂无评估运行。</td></tr>}
            </tbody>
          </table>
        </TableWrap>
      </Section>
    </div>
  );
}

function feedbackDistributionLabel(run: EvaluationRun) {
  const values = run.metrics.values ?? {};
  return `${feedbackLabel("false_positive")} ${metricText(values.falsePositiveCount)} · ${feedbackLabel("false_negative")} ${metricText(values.falseNegativeCount)} · 总数 ${metricText(values.feedbackCount)}`;
}

function metricText(value: unknown) {
  if (value === null || value === undefined || value === "") return "0";
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return jsonLabel(value);
}
