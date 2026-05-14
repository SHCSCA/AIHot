import { Rss } from "lucide-react";
import { useState } from "react";
import type { AdminApi } from "../api";
import { Section, TableWrap } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { useAsyncData } from "../hooks";
import type { DailyDigest, DailySection } from "../types";
import { categoryLabel } from "../labels";
import { channelLabel, formatDateTime, today } from "../utils";

export function DailyDigestsView({ api }: { api: AdminApi }) {
  const [filters, setFilters] = useState({ channel: "ai", date: today() });
  const { data: digests, reload, error } = useAsyncData(
    () => api.listDailyDigests({ channel: filters.channel, date: filters.date }),
    [] as DailyDigest[],
    [filters.channel, filters.date]
  );

  return (
    <div className="view-stack">
      <Section title="自动日报监控" description="日报由每小时流水线自动基于最近 24 小时精选情报生成并发布；这里仅查看结果和 RSS。">
        <div className="form-grid">
          <label>频道<select value={filters.channel} onChange={(event) => setFilters({ ...filters, channel: event.target.value })}><option value="ai">AI 热点</option><option value="amazon">Amazon 情报</option></select></label>
          <label>日期<input type="date" value={filters.date} onChange={(event) => setFilters({ ...filters, date: event.target.value })} /></label>
        </div>
        <div className="inline-actions"><a href={`/feed/${filters.channel}/daily.xml`}><Rss size={15} />RSS 链接</a><button onClick={reload}>刷新</button></div>
      </Section>
      <Section title="日报发布" error={error} action={<button onClick={reload}>刷新</button>}>
        <TableWrap>
          <table>
            <thead><tr><th>标题</th><th>频道</th><th>日期</th><th>状态</th><th>发布人</th><th>日报预览</th></tr></thead>
            <tbody>
              {digests.map((digest) => (
                <tr key={digest.id}>
                  <td><strong>{digest.title}</strong><span>{formatDateTime(digest.generatedAt)}</span></td><td>{channelLabel(digest.channel)}</td><td>{digest.date}</td><td><StatusLabel value={digest.published ? "published" : "unpublished"} /></td><td>{digest.publishedBy ?? "-"}</td><td><DailyPreview digest={digest} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
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
