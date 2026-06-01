import { Rss } from "lucide-react";
import { useState } from "react";
import type { AdminApi } from "../api";
import type { AdminChannel } from "../components/AdminChannelCards";
import { AdminChannelCards, usePersistedAdminChannel } from "../components/AdminChannelCards";
import { Section, TableWrap } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { useAsyncData } from "../hooks";
import type { DailyDigest, DailySection } from "../types";
import { actorLabel, categoryLabel } from "../labels";
import { channelLabel, formatDateTime, today } from "../utils";

export function DailyDigestsView({ api }: { api: AdminApi }) {
  const [channel, setChannel] = usePersistedAdminChannel("admin-daily-channel");
  const [filters, setFilters] = useState({ date: today() });
  const [strategyVersion, setStrategyVersion] = useState(defaultStrategyVersion(channel));
  const [runningAction, setRunningAction] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const { data: digests, reload, error } = useAsyncData(
    () => api.listDailyDigests({ channel, date: filters.date }),
    [] as DailyDigest[],
    [channel, filters.date]
  );
  const publishedCount = digests.filter((digest) => digest.published).length;
  const generatedCount = digests.length;

  function changeChannel(nextChannel: AdminChannel) {
    setChannel(nextChannel);
    setStrategyVersion(defaultStrategyVersion(nextChannel));
  }

  async function runAction(key: string, action: () => Promise<void>) {
    setRunningAction(key);
    setActionError(null);
    setActionSuccess(null);
    try {
      await action();
      await reload();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "日报操作失败。");
    } finally {
      setRunningAction(null);
    }
  }

  async function generateDigest() {
    await runAction("generate", async () => {
      const result = await api.generateDailyDigest({ channel, date: filters.date, strategyVersion });
      setActionSuccess(`${result.created ? "已生成" : "已更新"} ${result.dailyDigest.title}，纳入 ${result.eventCount} 条事件。`);
    });
  }

  async function publishDigest(digest: DailyDigest) {
    await runAction(`publish-${digest.id}`, async () => {
      await api.publishDailyDigest(digest.id, "operator");
      setActionSuccess(`已发布 ${digest.title}。`);
    });
  }

  async function unpublishDigest(digest: DailyDigest) {
    await runAction(`unpublish-${digest.id}`, async () => {
      await api.unpublishDailyDigest(digest.id, "operator");
      setActionSuccess(`已撤回 ${digest.title}。`);
    });
  }

  return (
    <div className="view-stack">
      <AdminChannelCards value={channel} onChange={changeChannel} metrics={[{ channel, metrics: { sourceCount: digests.length } }]} />
      <Section title="日报工作流" description="生成、预览、发布和撤回都走现有日报 API；发布状态与 RSS 输出分开确认。">
        <div className="stats-grid">
          <div className="metric"><span>已生成日报</span><strong>{generatedCount}</strong></div>
          <div className="metric metric-good"><span>已发布</span><strong>{publishedCount}</strong></div>
          <div className="metric metric-warn"><span>可撤回草稿/历史</span><strong>{generatedCount - publishedCount}</strong></div>
        </div>
      </Section>
      <Section title="生成与发布操作" description="操作区只包含会改变日报状态的动作；预览和状态在下方只读区确认。" error={actionError}>
        <div className="form-grid">
          <label>日期<input type="date" value={filters.date} onChange={(event) => setFilters({ ...filters, date: event.target.value })} /></label>
          <label>策略版本<input value={strategyVersion} onChange={(event) => setStrategyVersion(event.target.value)} /></label>
        </div>
        <div className="inline-actions"><button className="primary" onClick={generateDigest} disabled={runningAction !== null || !strategyVersion.trim()}>{runningAction === "generate" ? "生成中..." : "生成日报"}</button><a href={`/feed/${channel}/daily.xml`}><Rss size={15} />RSS 链接</a><button onClick={reload} disabled={runningAction !== null}>刷新</button></div>
        {actionSuccess && <p className="hint">{actionSuccess}</p>}
      </Section>
      <Section title="日报发布状态与预览" description="只读区展示生成时间、预览内容、发布人、发布时间和当前可执行状态。" error={error} action={<button onClick={reload} disabled={runningAction !== null}>刷新</button>}>
        <TableWrap>
          <table>
            <thead><tr><th>日报</th><th>生成</th><th>预览</th><th>发布状态</th><th>发布记录</th><th>操作</th></tr></thead>
            <tbody>
              {digests.map((digest) => (
                <tr key={digest.id}>
                  <td><strong>{digest.title}</strong><span>{channelLabel(digest.channel)} · {digest.date}</span></td>
                  <td>{formatDateTime(digest.generatedAt)}<span>策略：{digest.strategyVersion}</span></td>
                  <td><DailyPreview digest={digest} /></td>
                  <td><StatusLabel value={digest.published ? "published" : "unpublished"} /></td>
                  <td>{actorLabel(digest.publishedBy)}<span>{formatDateTime(digest.publishedAt)}</span></td>
                  <td>
                    <div className="inline-actions">
                      <button className="primary" onClick={() => publishDigest(digest)} disabled={runningAction !== null || digest.published}>{runningAction === `publish-${digest.id}` ? "发布中..." : "发布"}</button>
                      <button className="danger" onClick={() => unpublishDigest(digest)} disabled={runningAction !== null || !digest.published}>{runningAction === `unpublish-${digest.id}` ? "撤回中..." : "撤回"}</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
        {!digests.length && <p className="hint">当前日期暂无日报，可在上方生成。</p>}
      </Section>
    </div>
  );
}

function DailyPreview({ digest }: { digest: DailyDigest }) {
  const sections = digestSections(digest);
  if (!sections.length) return <span className="hint">暂无分区内容</span>;
  return (
    <div className="admin-daily-preview">
      {sections.slice(0, 4).map((section) => (
        <span key={section.category}>
          {categoryLabel(section.category)} · {section.count} 篇
        </span>
      ))}
      {sections[0]?.items?.[0]?.title && <strong>{sections[0].items[0].title}</strong>}
    </div>
  );
}

function digestSections(digest: DailyDigest): DailySection[] {
  const raw = digest.sections as Record<string, unknown>;
  if (Array.isArray(raw?.sections)) return raw.sections as DailySection[];
  if (Array.isArray(digest.sections)) return digest.sections as DailySection[];
  const highlights = Array.isArray(raw?.highlights) ? raw.highlights : [];
  const grouped = new Map<string, DailySection>();
  highlights.forEach((entry) => {
    if (!entry || typeof entry !== "object") return;
    const item = entry as Record<string, unknown>;
    const category = String(item.category || "industry");
    const section = grouped.get(category) ?? { category, label: categoryLabel(category), count: 0, items: [] };
    section.count += 1;
    grouped.set(category, section);
  });
  return [...grouped.values()];
}

function defaultStrategyVersion(channel: AdminChannel) {
  return `${channel}-default-v1`;
}
