import { Rss } from "lucide-react";
import { useState } from "react";
import type { AdminApi } from "../api";
import { Section, TableWrap } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { useAsyncData } from "../hooks";
import type { DailyDigest } from "../types";
import { channelLabel, formatDateTime, jsonLabel, today } from "../utils";

export function DailyDigestsView({ api }: { api: AdminApi }) {
  const [form, setForm] = useState({ channel: "ai", date: today(), strategyVersion: "ai-default-v1" });
  const { data: digests, reload, error } = useAsyncData(() => api.listDailyDigests({ channel: form.channel }), [] as DailyDigest[]);

  async function generate() {
    await api.generateDailyDigest(form);
    reload();
  }

  async function toggle(digest: DailyDigest) {
    if (digest.published) await api.unpublishDailyDigest(digest.id);
    else await api.publishDailyDigest(digest.id);
    reload();
  }

  return (
    <div className="view-stack">
      <Section title="生成日报" description="从精选事件生成日报，发布后 public daily 与 RSS 可读取。">
        <div className="form-grid">
          <label>频道<select value={form.channel} onChange={(event) => setForm({ ...form, channel: event.target.value })}><option value="ai">AI 热点</option><option value="amazon">Amazon 情报</option></select></label>
          <label>日期<input type="date" value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} /></label>
          <label>策略版本<input value={form.strategyVersion} onChange={(event) => setForm({ ...form, strategyVersion: event.target.value })} /></label>
        </div>
        <div className="inline-actions"><button className="primary" onClick={generate}>生成日报</button><a href={`/feed/${form.channel}/daily.xml`}><Rss size={15} />RSS 链接</a></div>
      </Section>
      <Section title="日报发布" error={error} action={<button onClick={reload}>刷新</button>}>
        <TableWrap>
          <table>
            <thead><tr><th>标题</th><th>频道</th><th>日期</th><th>状态</th><th>发布人</th><th>预览</th><th>操作</th></tr></thead>
            <tbody>
              {digests.map((digest) => (
                <tr key={digest.id}>
                  <td><strong>{digest.title}</strong><span>{formatDateTime(digest.generatedAt)}</span></td><td>{channelLabel(digest.channel)}</td><td>{digest.date}</td><td><StatusLabel value={digest.published ? "published" : "unpublished"} /></td><td>{digest.publishedBy ?? "-"}</td><td><code>{jsonLabel(digest.sections)}</code></td>
                  <td><button className={digest.published ? "danger ghost" : "primary"} onClick={() => toggle(digest)}>{digest.published ? "取消发布" : "发布"}</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Section>
    </div>
  );
}
