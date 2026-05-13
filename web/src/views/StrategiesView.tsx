import { useState } from "react";
import type { AdminApi } from "../api";
import { Section, TableWrap } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { useAsyncData } from "../hooks";
import type { StrategyVersion } from "../types";
import { channelLabel, jsonLabel } from "../utils";

export function StrategiesView({ api }: { api: AdminApi }) {
  const { data: strategies, reload, error } = useAsyncData(() => api.listStrategies(), [] as StrategyVersion[]);
  const [form, setForm] = useState({ id: "ai-default-v1", channel: "ai", name: "AI 默认精选策略", threshold: "72" });
  async function createStrategy() {
    await api.createStrategy({
      id: form.id,
      channel: form.channel,
      name: form.name,
      status: "draft",
      prefilterPromptVersion: "prefilter-v1",
      scorePromptVersion: "score-v1",
      rankFormulaVersion: "rank-policy-v1",
      thresholds: { selected: Number(form.threshold) },
      modelConfig: { provider: "fake" }
    });
    reload();
  }
  async function activate(strategy: StrategyVersion) {
    await api.activateStrategy(strategy.id);
    reload();
  }
  return (
    <div className="view-stack split-layout">
      <Section title="新建策略版本" description="创建草稿策略后再激活，同一频道只保留一个生效策略。">
        <div className="form-grid">
          <label>策略 ID<input value={form.id} onChange={(event) => setForm({ ...form, id: event.target.value })} /></label>
          <label>频道<select value={form.channel} onChange={(event) => setForm({ ...form, channel: event.target.value })}><option value="ai">AI 热点</option><option value="amazon">Amazon 情报</option></select></label>
          <label>名称<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
          <label>精选阈值<input value={form.threshold} onChange={(event) => setForm({ ...form, threshold: event.target.value })} /></label>
        </div>
        <button className="primary" onClick={createStrategy}>创建策略</button>
      </Section>
      <Section title="策略版本" error={error} action={<button onClick={reload}>刷新</button>}>
        <TableWrap>
          <table>
            <thead><tr><th>ID</th><th>频道</th><th>名称</th><th>状态</th><th>阈值</th><th>操作</th></tr></thead>
            <tbody>{strategies.map((strategy) => <tr key={strategy.id}><td>{strategy.id}</td><td>{channelLabel(strategy.channel)}</td><td>{strategy.name}</td><td><StatusLabel value={strategy.status} /></td><td><code>{jsonLabel(strategy.thresholds)}</code></td><td><button className="primary" onClick={() => activate(strategy)} disabled={strategy.status === "active"}>激活</button></td></tr>)}</tbody>
          </table>
        </TableWrap>
      </Section>
    </div>
  );
}
