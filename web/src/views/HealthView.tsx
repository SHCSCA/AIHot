import type { AdminApi } from "../api";
import { MetricCard, MetricGrid } from "../components/MetricCard";
import { Section, TableWrap } from "../components/Section";
import { useAsyncData } from "../hooks";
import type { SourceState } from "../types";
import { channelLabel, formatDateTime, formatPercent } from "../utils";

export function HealthView({ api }: { api: AdminApi }) {
  const { data: states, reload, error } = useAsyncData(() => api.listSourceStates(), [] as SourceState[]);
  const average = states.length ? Math.round(states.reduce((total, state) => total + state.healthScore, 0) / states.length) : 0;
  const warnings = states.filter((state) => state.errorStreak > 0 || state.healthScore < 80).length;
  return (
    <div className="view-stack">
      <MetricGrid>
        <MetricCard label="平均健康分" value={average} tone={average >= 80 ? "good" : "warn"} />
        <MetricCard label="需关注信源" value={warnings} tone={warnings ? "warn" : "good"} />
        <MetricCard label="监控对象" value={states.length} />
      </MetricGrid>
      <Section title="健康监控" error={error} action={<button onClick={reload}>刷新</button>}>
        <TableWrap>
          <table>
            <thead><tr><th>信源</th><th>频道</th><th>健康分</th><th>连续错误</th><th>重复率</th><th>噪声率</th><th>最近成功</th><th>下次抓取</th></tr></thead>
            <tbody>
              {states.map((state) => (
                <tr key={state.sourceId}>
                  <td><strong>{state.sourceName}</strong><span>{state.sourceId}</span></td>
                  <td>{channelLabel(state.channel)}</td><td>{state.healthScore}</td><td>{state.errorStreak}</td>
                  <td>{formatPercent(state.duplicateRatio)}</td><td>{formatPercent(state.noiseRatio)}</td>
                  <td>{formatDateTime(state.lastSuccessAt)}</td><td>{formatDateTime(state.nextFetchAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Section>
    </div>
  );
}
