import { useState } from "react";
import type { AdminApi } from "../api";
import { AdminChannelCards, usePersistedAdminChannel } from "../components/AdminChannelCards";
import { MetricCard, MetricGrid } from "../components/MetricCard";
import { Section, TableWrap } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { useAsyncData } from "../hooks";
import type { StrategyVersion } from "../types";
import { channelLabel, jsonLabel } from "../utils";

export function StrategiesView({ api }: { api: AdminApi }) {
  const [channel, setChannel] = usePersistedAdminChannel("admin-strategies-channel");
  const { data: strategies, reload, error } = useAsyncData(() => api.listStrategies(channel), [] as StrategyVersion[], [channel]);
  const [form, setForm] = useState({ id: "ai-default-v1", name: "AI 默认精选策略", threshold: "72" });
  const activeStrategy = strategies.find((strategy) => strategy.status === "active");
  const draftCount = strategies.filter((strategy) => strategy.status === "draft").length;
  async function createStrategy() {
    await api.createStrategy({
      id: form.id,
      channel,
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
      <Section
        title="Lab Mode · 策略配置"
        description="小步管理频道级精选策略：先创建草稿版本，再激活为当前生产策略。创建和激活继续复用现有策略版本接口。"
      >
        <AdminChannelCards value={channel} onChange={setChannel} metrics={[{ channel, metrics: { sourceCount: strategies.length } }]} />
        <MetricGrid>
          <MetricCard label="当前频道" value={channelLabel(channel)} />
          <MetricCard label="活跃版本" value={activeStrategy?.id ?? "未激活"} tone={activeStrategy ? "good" : "warn"} />
          <MetricCard label="草稿版本" value={draftCount} />
        </MetricGrid>
        <div className="lab-mode-panel" aria-label="当前生效策略">
          <div>
            <span>版本</span>
            <strong>{activeStrategy?.name ?? "暂无生效策略"}</strong>
            <code>{activeStrategy?.id ?? "未设置"}</code>
          </div>
          <div>
            <span>精选阈值</span>
            <strong>{jsonLabel(activeStrategy?.thresholds)}</strong>
          </div>
          <div>
            <span>模型配置</span>
            <strong>{jsonLabel(activeStrategy?.modelConfig)}</strong>
          </div>
          <div>
            <span>激活状态</span>
            {activeStrategy ? <StatusLabel value={activeStrategy.status} /> : <strong>等待激活</strong>}
          </div>
        </div>
      </Section>
      <Section title="创建策略草稿" description="仅填写当前接口支持的策略 ID、名称和精选阈值；Prompt 与排序公式沿用现有默认版本。">
        <div className="form-grid">
          <label>策略 ID<input value={form.id} onChange={(event) => setForm({ ...form, id: event.target.value })} /></label>
          <label>名称<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
          <label>精选阈值<input value={form.threshold} onChange={(event) => setForm({ ...form, threshold: event.target.value })} /></label>
        </div>
        <button className="primary" onClick={createStrategy}>创建策略</button>
      </Section>
      <Section title="策略版本库" description="按版本查看阈值、模型配置和激活状态；同一频道只应保留一个 active 版本。" error={error} action={<button onClick={reload}>刷新</button>}>
        <TableWrap>
          <table>
            <thead><tr><th>版本</th><th>频道</th><th>状态</th><th>阈值</th><th>模型配置</th><th>操作</th></tr></thead>
            <tbody>
              {strategies.map((strategy) => (
                <tr key={strategy.id}>
                  <td><strong>{strategy.name}</strong><span>{strategy.id}</span></td>
                  <td>{channelLabel(strategy.channel)}</td>
                  <td><StatusLabel value={strategy.status} /></td>
                  <td><code>{jsonLabel(strategy.thresholds)}</code></td>
                  <td><code>{jsonLabel(strategy.modelConfig)}</code></td>
                  <td><button className="primary" onClick={() => activate(strategy)} disabled={strategy.status === "active"}>激活</button></td>
                </tr>
              ))}
              {strategies.length === 0 && <tr><td colSpan={6}>当前频道暂无策略版本。</td></tr>}
            </tbody>
          </table>
        </TableWrap>
      </Section>
    </div>
  );
}
