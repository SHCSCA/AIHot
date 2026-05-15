import type { AdminApi } from "../api";
import { AdminChannelCards, type AdminChannel, usePersistedAdminChannel } from "../components/AdminChannelCards";
import { MetricCard, MetricGrid } from "../components/MetricCard";
import { Section, TableWrap } from "../components/Section";
import { useAsyncData } from "../hooks";
import { categoryLabel, collectionStatusLabel, sourceGroupLabel } from "../labels";
import type { ChannelQuality, QualityDashboard } from "../types";
import { channelLabel, formatDateTime, formatPercent } from "../utils";
import { useState } from "react";

const emptyQuality: QualityDashboard = {
  windowHours: 24,
  generatedAt: "",
  channels: []
};

type QualityTab = "funnel" | "rejections" | "sources";

export function QualityView({ api }: { api: AdminApi }) {
  const [channel, setChannel] = usePersistedAdminChannel("admin-quality-channel");
  const [tab, setTab] = useState<QualityTab>("funnel");
  const { data, error, reload, loading } = useAsyncData(() => api.getQualityDashboard({ window: 24 }), emptyQuality);
  const active = data.channels.find((item) => item.channel === channel) ?? data.channels[0];
  const metrics = active?.metrics;
  const channelMetrics = data.channels.map((item) => ({
    channel: item.channel,
    metrics: { sourceCount: item.metrics.sourceCount }
  }));

  return (
    <div className="view-stack">
      <AdminChannelCards value={channel} onChange={(next) => { setChannel(next); setTab("funnel"); }} metrics={channelMetrics} />
      <MetricGrid>
        <MetricCard label="原始条目" value={metrics?.rawDocuments ?? 0} />
        <MetricCard label="初筛通过" value={metrics?.acceptedScreenings ?? 0} tone={(metrics?.acceptedScreenings ?? 0) ? "good" : "warn"} />
        <MetricCard label="精选条目" value={metrics?.selectedItems ?? 0} tone={(metrics?.selectedItems ?? 0) ? "good" : "warn"} />
        <MetricCard label="公开精选" value={metrics?.publicSelectedEvents ?? 0} tone={(metrics?.publicSelectedEvents ?? 0) ? "good" : "warn"} />
      </MetricGrid>
      <Section
        title="质量校准"
        description={`基于最近 ${data.windowHours} 小时的抓取、初筛、精筛、精选和发布漏斗。最后更新：${formatDateTime(data.generatedAt)}`}
        error={error}
        action={<button onClick={reload}>{loading ? "刷新中..." : "刷新"}</button>}
      >
        {active ? (
          <QualityChannel channel={active} tab={tab} onTabChange={setTab} />
        ) : (
          <p className="hint">暂无质量数据。</p>
        )}
      </Section>
    </div>
  );
}

function QualityChannel({ channel, tab, onTabChange }: { channel: ChannelQuality; tab: QualityTab; onTabChange: (tab: QualityTab) => void }) {
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
      <div className="quality-tabs" role="tablist" aria-label="质量视图">
        <button className={tab === "funnel" ? "active" : ""} onClick={() => onTabChange("funnel")}>漏斗概览</button>
        <button className={tab === "rejections" ? "active" : ""} onClick={() => onTabChange("rejections")}>拒绝样本</button>
        <button className={tab === "sources" ? "active" : ""} onClick={() => onTabChange("sources")}>信源贡献</button>
      </div>
      {tab === "funnel" && <QualityFunnel channel={channel} />}
      {tab === "rejections" && <QualityRejections channel={channel} />}
      {tab === "sources" && <QualitySources channel={channel} />}
    </article>
  );
}

function QualityFunnel({ channel }: { channel: ChannelQuality }) {
  const metrics = channel.metrics;
  return (
    <>
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
    </>
  );
}

function QualityRejections({ channel }: { channel: ChannelQuality }) {
  return (
    <TableWrap>
      <table>
        <thead><tr><th>被拒文章</th><th>原因</th><th>信源</th><th>分类</th><th>时间</th></tr></thead>
        <tbody>
          {channel.rejectionSamples.map((sample) => (
            <tr key={sample.rawDocumentId}>
              <td>
                <strong>{sample.title || "未命名文章"}</strong>
                <span>{sample.summary || "暂无文章描述。"}</span>
                {sample.url && <a href={sample.url} target="_blank" rel="noreferrer">查看原文</a>}
              </td>
              <td><strong>{sample.reason || sample.reasonCode}</strong><span>{sample.reasonCode} · {sample.bucket} · 置信度 {Math.round(sample.confidenceScore)}</span></td>
              <td><strong>{sample.sourceName}</strong><span>{sample.sourceId} · {sourceGroupLabel(sample.sourceGroup)}</span></td>
              <td>{categoryLabel(sample.category)}</td>
              <td>{formatDateTime(sample.createdAt)}</td>
            </tr>
          ))}
          {channel.rejectionSamples.length === 0 && <tr><td colSpan={5}>暂无拒绝样本。</td></tr>}
        </tbody>
      </table>
    </TableWrap>
  );
}

function QualitySources({ channel }: { channel: ChannelQuality }) {
  return (
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
