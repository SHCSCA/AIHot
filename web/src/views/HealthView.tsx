import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import type { AdminApi } from "../api";
import { AdminChannelCards, type AdminChannel, usePersistedAdminChannel } from "../components/AdminChannelCards";
import { MetricCard, MetricGrid } from "../components/MetricCard";
import { PaginationBar } from "../components/PaginationBar";
import { Section, TableWrap } from "../components/Section";
import { collectionStatusLabel, diagnosticStatusLabel, screenReasonCodeLabel, sourceGroupLabel } from "../labels";
import type { Page, SourceDiagnostic } from "../types";
import { channelLabel, formatDateTime, formatPercent } from "../utils";

const PAGE_SIZE = 50;

type HealthFilters = {
  q: string;
  sourceGroup: string;
  collectionStatus: string;
  freeAccess: string;
  diagnosticStatus: string;
  sort: string;
};

const emptyPage: Page<SourceDiagnostic> = {
  items: [],
  count: 0,
  page: 1,
  pageSize: PAGE_SIZE,
  total: 0,
  totalPages: 1,
  hasNext: false,
  nextCursor: null,
  metrics: {}
};

export function HealthView({ api }: { api: AdminApi }) {
  const [channel, setChannel] = usePersistedAdminChannel("admin-health-channel");
  const [filters, setFilters] = useState<HealthFilters>({
    q: "",
    sourceGroup: "",
    collectionStatus: "",
    freeAccess: "",
    diagnosticStatus: "",
    sort: "updated_desc"
  });
  const [diagnosticPage, setDiagnosticPage] = useState<Page<SourceDiagnostic>>(emptyPage);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [channel, filters.q, filters.sourceGroup, filters.collectionStatus, filters.freeAccess, filters.diagnosticStatus, filters.sort]);

  useEffect(() => {
    void loadPage(page);
  }, [api, channel, filters.q, filters.sourceGroup, filters.collectionStatus, filters.freeAccess, filters.diagnosticStatus, filters.sort, page]);

  async function loadPage(pageNumber = 1) {
    setLoading(true);
    try {
      const nextPage = await api.listSourceDiagnosticsPage({
        channel,
        q: filters.q || undefined,
        sourceGroup: filters.sourceGroup || undefined,
        collectionStatus: filters.collectionStatus || undefined,
        freeAccess: filters.freeAccess || undefined,
        diagnosticStatus: filters.diagnosticStatus || undefined,
        sort: filters.sort,
        page: pageNumber,
        pageSize: PAGE_SIZE
      });
      setDiagnosticPage(nextPage);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "健康监控加载失败");
    } finally {
      setLoading(false);
    }
  }

  const metrics = diagnosticPage.metrics ?? {};
  const channelMetrics = [
    { channel: "ai", metrics: channel === "ai" ? { sourceCount: metrics.sourceCount } : {} },
    { channel: "amazon", metrics: channel === "amazon" ? { sourceCount: metrics.sourceCount } : {} }
  ];

  return (
    <div className="view-stack">
      <AdminChannelCards value={channel} onChange={setChannel} metrics={channelMetrics} />
      <MetricGrid>
        <MetricCard label="平均健康分" value={metrics.averageHealthScore ?? 0} tone={(metrics.averageHealthScore ?? 0) >= 80 ? "good" : "warn"} />
        <MetricCard label="可用信源" value={metrics.usableCount ?? 0} tone={(metrics.usableCount ?? 0) ? "good" : "warn"} />
        <MetricCard label="需处理信源" value={metrics.warningCount ?? 0} tone={(metrics.warningCount ?? 0) ? "warn" : "good"} />
        <MetricCard label="缺少发布时间" value={metrics.missingDateCount ?? 0} tone={(metrics.missingDateCount ?? 0) ? "bad" : "good"} />
      </MetricGrid>
      <Section
        title="健康监控"
        description={`${channelLabel(channel)} · ${diagnosticPage.total ?? 0} 条匹配信源`}
        error={error}
        action={<button onClick={() => loadPage(page)}>{loading ? "刷新中..." : "刷新"}</button>}
      >
        <HealthFilterPanel filters={filters} onChange={(next) => setFilters({ ...filters, ...next })} />
        <TableWrap>
          <table>
            <thead>
              <tr>
                <th>信源</th>
                <th>频道</th>
                <th>可用性诊断</th>
                <th>健康分</th>
                <th>候选/接收</th>
                <th>跳过原因</th>
                <th>AI 初筛</th>
                <th>最近抓取</th>
                <th>下次抓取</th>
              </tr>
            </thead>
            <tbody>
              {diagnosticPage.items.map((source) => (
                <tr key={source.sourceId}>
                  <td>
                    <strong>{source.sourceName}</strong>
                    <span>{source.sourceId} · {source.tier} · {sourceGroupLabel(source.sourceGroup)}</span>
                  </td>
                  <td>{channelLabel(source.channel)}</td>
                  <td>
                    <span className={`status diagnostic-${source.diagnosticStatus}`}>
                      {diagnosticStatusLabel(source.diagnosticStatus)}
                    </span>
                    <span>{collectionStatusLabel(source.collectionStatus)} · {source.freeAccess ? "免费可读" : "需授权"}</span>
                    {source.screening.latestReason && <span>{source.screening.latestReason}</span>}
                  </td>
                  <td>
                    <strong>{Math.round(source.healthScore)}</strong>
                    <span>错误 {source.errorStreak} · 重复 {formatPercent(source.duplicateRatio)}</span>
                  </td>
                  <td>
                    {source.lastRun ? (
                      <>
                        <strong>{source.lastRun.candidateItems} / {source.lastRun.acceptedItems}</strong>
                        <span>原始 {source.rawCount24h} · 条目 {source.lastRun.itemCount}</span>
                      </>
                    ) : "暂无抓取"}
                  </td>
                  <td>
                    {source.lastRun ? (
                      <>
                        <strong>旧 {source.lastRun.skippedOldItems}</strong>
                        <span>缺时间 {source.lastRun.skippedMissingDate} · 链接无效 {source.lastRun.skippedInvalidOriginalUrl}</span>
                      </>
                    ) : "-"}
                  </td>
                  <td>
                    <strong>{source.screening.accepted24h} 通过</strong>
                    <span>{source.screening.rejected24h} 拒绝 · {source.screening.latestReasonCode ? screenReasonCodeLabel(source.screening.latestReasonCode) : "无原因"}</span>
                  </td>
                  <td>{formatDateTime(source.lastRun?.startedAt ?? source.lastSuccessAt)}</td>
                  <td>{formatDateTime(source.nextFetchAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
        <PaginationBar page={page} totalPages={diagnosticPage.totalPages ?? 1} onPageChange={setPage} disabled={loading} />
      </Section>
    </div>
  );
}

function HealthFilterPanel({ filters, onChange }: { filters: HealthFilters; onChange: (filters: Partial<HealthFilters>) => void }) {
  return (
    <div className="admin-filter-panel">
      <label className="admin-search"><Search size={16} /><input aria-label="搜索健康信源" placeholder="搜索名称 / ID / URL" value={filters.q} onChange={(event) => onChange({ q: event.target.value })} /></label>
      <label>健康状态<select aria-label="健康状态" value={filters.diagnosticStatus} onChange={(event) => onChange({ diagnosticStatus: event.target.value })}><option value="">全部状态</option><option value="usable">可用</option><option value="waiting">等待抓取</option><option value="fetch_failed">抓取失败</option><option value="missing_publish_time">缺少发布时间</option><option value="invalid_original_url">原文链接无效</option><option value="no_current_items">无最近内容</option><option value="no_accepted_items">无有效条目</option><option value="pending_api,rate_limited,unavailable,disabled">接入异常</option></select></label>
      <label>信源类型<select aria-label="健康信源类型" value={filters.sourceGroup} onChange={(event) => onChange({ sourceGroup: event.target.value })}><option value="">全部类型</option><option value="official,first_party">官方/一手</option><option value="media">资讯</option><option value="social,community">社媒/社区</option><option value="vendor">服务商</option></select></label>
      <label>收集状态<select aria-label="健康收集状态" value={filters.collectionStatus} onChange={(event) => onChange({ collectionStatus: event.target.value })}><option value="">全部</option><option value="collectable">可抓取</option><option value="pending_api">待接入</option><option value="rate_limited">限流</option><option value="unavailable">不可用</option></select></label>
      <label>访问方式<select aria-label="访问方式" value={filters.freeAccess} onChange={(event) => onChange({ freeAccess: event.target.value })}><option value="">全部</option><option value="true">免费可读</option><option value="false">需授权</option></select></label>
      <label>排序<select aria-label="健康排序" value={filters.sort} onChange={(event) => onChange({ sort: event.target.value })}><option value="updated_desc">最近更新</option><option value="health_asc">健康分低优先</option><option value="error_desc">错误次数高优先</option><option value="last_error">最近错误</option><option value="next_fetch">下次抓取</option></select></label>
    </div>
  );
}
