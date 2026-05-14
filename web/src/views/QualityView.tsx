import type { AdminApi } from "../api";
import { MetricCard, MetricGrid } from "../components/MetricCard";
import { Section, TableWrap } from "../components/Section";
import { useAsyncData } from "../hooks";
import { categoryLabel, collectionStatusLabel, sourceGroupLabel } from "../labels";
import type { ChannelQuality, QualityDashboard } from "../types";
import { channelLabel, formatDateTime, formatPercent } from "../utils";

const emptyQuality: QualityDashboard = {
  windowHours: 24,
  generatedAt: "",
  channels: []
};

export function QualityView({ api }: { api: AdminApi }) {
  const { data, error, reload, loading } = useAsyncData(() => api.getQualityDashboard({ window: 24 }), emptyQuality);
  const totals = data.channels.reduce(
    (acc, channel) => ({
      raw: acc.raw + channel.metrics.rawDocuments,
      accepted: acc.accepted + channel.metrics.acceptedScreenings,
      selected: acc.selected + channel.metrics.selectedItems,
      publicSelected: acc.publicSelected + channel.metrics.publicSelectedEvents
    }),
    { raw: 0, accepted: 0, selected: 0, publicSelected: 0 }
  );

  return (
    <div className="view-stack">
      <MetricGrid>
        <MetricCard label="原始条目" value={totals.raw} />
        <MetricCard label="初筛通过" value={totals.accepted} tone={totals.accepted ? "good" : "warn"} />
        <MetricCard label="精选条目" value={totals.selected} tone={totals.selected ? "good" : "warn"} />
        <MetricCard label="公开精选" value={totals.publicSelected} tone={totals.publicSelected ? "good" : "warn"} />
      </MetricGrid>
      <Section
        title="质量校准"
        description={`基于最近 ${data.windowHours} 小时的抓取、初筛、精筛、精选和发布漏斗。最后更新：${formatDateTime(data.generatedAt)}`}
        error={error}
        action={<button onClick={reload}>{loading ? "刷新中..." : "刷新"}</button>}
      >
        <div className="quality-channel-stack">
          {data.channels.map((channel) => (
            <QualityChannel key={channel.channel} channel={channel} />
          ))}
        </div>
      </Section>
    </div>
  );
}

function QualityChannel({ channel }: { channel: ChannelQuality }) {
  const metrics = channel.metrics;
  return (
    <article className="quality-card">
      <div className="quality-card-head">
        <div>
          <h3>{channelLabel(channel.channel)}质量漏斗</h3>
          <p>{metrics.enabledSourceCount} 个启用信源 · {metrics.fetchRuns} 次抓取 · 成功率 {formatPercent(channel.conversion.fetchSuccessRate)}</p>
        </div>
        <strong>{formatPercent(channel.conversion.screenAcceptRate)} 初筛通过率</strong>
      </div>
      <div className="quality-funnel" aria-label={`${channelLabel(channel.channel)}漏斗`}>
        <FunnelStep label="原始条目" value={metrics.rawDocuments} />
        <FunnelStep label="AI 初筛" value={metrics.acceptedScreenings} sub={`${metrics.rejectedScreenings} 拒绝`} />
        <FunnelStep label="中文入库" value={metrics.normalizedItems} />
        <FunnelStep label="精筛评分" value={metrics.scoredItems} />
        <FunnelStep label="精选" value={metrics.selectedItems} sub={`${formatPercent(channel.conversion.selectedRate)} 精选率`} />
        <FunnelStep label="公开发布" value={metrics.publicSelectedEvents} sub={`${metrics.approvedEvents} 已通过`} />
      </div>
      <div className="quality-bottlenecks">
        {channel.bottlenecks.map((item) => <span key={item}>{item}</span>)}
      </div>
      <div className="quality-tables">
        <TableWrap>
          <table>
            <thead><tr><th>拒绝原因</th><th>分组</th><th>数量</th></tr></thead>
            <tbody>
              {channel.rejectionReasons.map((reason) => (
                <tr key={`${reason.reasonCode}-${reason.bucket}`}>
                  <td><strong>{reason.reason || reason.reasonCode}</strong><span>{reason.reasonCode}</span></td>
                  <td>{reason.bucket}</td>
                  <td>{reason.count}</td>
                </tr>
              ))}
              {channel.rejectionReasons.length === 0 && <tr><td colSpan={3}>暂无拒绝原因。</td></tr>}
            </tbody>
          </table>
        </TableWrap>
        <TableWrap>
          <table>
            <thead><tr><th>分类</th><th>评分</th><th>精选</th><th>发布</th></tr></thead>
            <tbody>
              {channel.categoryBreakdown.map((category) => (
                <tr key={category.category}>
                  <td>{categoryLabel(category.category)}</td>
                  <td>{category.scoredItems}</td>
                  <td>{category.selectedItems}</td>
                  <td>{category.approvedEvents}</td>
                </tr>
              ))}
              {channel.categoryBreakdown.length === 0 && <tr><td colSpan={4}>暂无分类数据。</td></tr>}
            </tbody>
          </table>
        </TableWrap>
      </div>
      <TableWrap>
        <table>
          <thead><tr><th>信源贡献</th><th>状态</th><th>原始</th><th>初筛通过</th><th>精选</th></tr></thead>
          <tbody>
            {channel.sourceContributions.map((source) => (
              <tr key={source.sourceId}>
                <td><strong>{source.sourceName}</strong><span>{source.sourceId} · {source.tier} · {sourceGroupLabel(source.sourceGroup)}</span></td>
                <td>{collectionStatusLabel(source.collectionStatus)} · 健康 {Math.round(source.healthScore)}</td>
                <td>{source.rawDocuments}</td>
                <td>{source.acceptedScreenings}</td>
                <td>{source.selectedItems}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
    </article>
  );
}

function FunnelStep({ label, value, sub }: { label: string; value: number; sub?: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
      {sub && <em>{sub}</em>}
    </div>
  );
}
