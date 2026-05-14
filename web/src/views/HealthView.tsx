import { useEffect, useState } from "react";
import type { AdminApi } from "../api";
import { MetricCard, MetricGrid } from "../components/MetricCard";
import { Section, TableWrap } from "../components/Section";
import { collectionStatusLabel, diagnosticStatusLabel, sourceGroupLabel } from "../labels";
import type { SourceDiagnostic } from "../types";
import { channelLabel, formatDateTime, formatPercent } from "../utils";

export function HealthView({ api }: { api: AdminApi }) {
  const [diagnostics, setDiagnostics] = useState<SourceDiagnostic[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasNext, setHasNext] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  useEffect(() => {
    void loadFirstPage();
  }, [api]);

  async function loadFirstPage() {
    setLoading(true);
    try {
      const page = await api.listSourceDiagnosticsPage({ take: 50 });
      setDiagnostics(page.items);
      setHasNext(page.hasNext);
      setNextCursor(page.nextCursor);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "健康监控加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadMore() {
    if (!nextCursor || loading) return;
    setLoading(true);
    try {
      const page = await api.listSourceDiagnosticsPage({ take: 50, cursor: nextCursor });
      setDiagnostics((current) => [...current, ...page.items]);
      setHasNext(page.hasNext);
      setNextCursor(page.nextCursor);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "健康监控加载失败");
    } finally {
      setLoading(false);
    }
  }
  const average = diagnostics.length
    ? Math.round(diagnostics.reduce((total, source) => total + source.healthScore, 0) / diagnostics.length)
    : 0;
  const usable = diagnostics.filter((source) => source.diagnosticStatus === "usable").length;
  const warnings = diagnostics.filter((source) => isWarning(source.diagnosticStatus)).length;
  const missingDate = diagnostics.filter((source) => source.diagnosticStatus === "missing_publish_time").length;
  return (
    <div className="view-stack">
      <MetricGrid>
        <MetricCard label="平均健康分" value={average} tone={average >= 80 ? "good" : "warn"} />
        <MetricCard label="可用信源" value={usable} tone={usable ? "good" : "warn"} />
        <MetricCard label="需处理信源" value={warnings} tone={warnings ? "warn" : "good"} />
        <MetricCard label="缺少发布时间" value={missingDate} tone={missingDate ? "bad" : "good"} />
      </MetricGrid>
      <Section title="健康监控" error={error} action={<button onClick={loadFirstPage}>刷新</button>}>
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
              {diagnostics.map((source) => (
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
                    <span>{source.screening.rejected24h} 拒绝 · {source.screening.latestReasonCode ?? "无原因"}</span>
                  </td>
                  <td>{formatDateTime(source.lastRun?.startedAt ?? source.lastSuccessAt)}</td>
                  <td>{formatDateTime(source.nextFetchAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
        {hasNext && <button className="load-more" onClick={loadMore} disabled={loading}>{loading ? "正在加载..." : "加载更多健康记录"}</button>}
      </Section>
    </div>
  );
}

function isWarning(status: string) {
  return !["usable", "waiting"].includes(status);
}
