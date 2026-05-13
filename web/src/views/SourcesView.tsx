import { Power, PowerOff } from "lucide-react";
import { useState } from "react";
import type { AdminApi } from "../api";
import { MetricCard, MetricGrid } from "../components/MetricCard";
import { Section, TableWrap } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { useAsyncData } from "../hooks";
import { collectionStatusLabel, sourceGroupLabel, sourceTypeLabel } from "../labels";
import type { Source } from "../types";
import { adapterLabel, channelLabel, visibilityLabel } from "../utils";

const newSource: Source = {
  id: "",
  channel: "ai",
  sourceType: "html",
  tier: "T2",
  name: "",
  url: "",
  language: "en",
  region: "global",
  authorityWeight: 80,
  noiseLevel: 0.1,
  fetchAdapter: "http_article",
  parserType: "website",
  defaultCategories: ["industry"],
  fetchIntervalMinutes: 720,
  enabled: true,
  visibility: "public",
  sourceGroup: "media",
  contributorNo: "",
  socialHandle: "",
  collectionStatus: "collectable",
  freeAccess: true,
  notes: ""
};

export function SourcesView({ api }: { api: AdminApi }) {
  const { data: sources, reload, error } = useAsyncData(() => api.listSources(), [] as Source[]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Source | null>(null);
  const [form, setForm] = useState<Source>(newSource);
  const filtered = sources.filter((source) => `${source.name} ${source.id}`.toLowerCase().includes(query.toLowerCase()));

  async function toggle(source: Source) {
    await api.patchSource(source.id, { enabled: !source.enabled });
    reload();
  }

  async function submit() {
    await api.createSource(form);
    setForm(newSource);
    reload();
  }

  return (
    <div className="view-stack split-layout">
      <div className="view-stack">
        <MetricGrid>
          <MetricCard label="信源总数" value={sources.length} />
          <MetricCard label="已启用" value={sources.filter((source) => source.enabled).length} tone="good" />
          <MetricCard label="高权威源" value={sources.filter((source) => source.authorityWeight >= 90).length} />
          <MetricCard label="待接入社媒" value={sources.filter((source) => source.sourceGroup === "social" && source.collectionStatus !== "collectable").length} tone="warn" />
        </MetricGrid>
        <Section title="信源列表" error={error} action={<input placeholder="搜索信源" value={query} onChange={(event) => setQuery(event.target.value)} />}>
          <TableWrap>
            <table>
              <thead><tr><th>信源</th><th>频道</th><th>类型</th><th>等级</th><th>采集方式</th><th>间隔</th><th>可见性</th><th>状态</th><th>操作</th></tr></thead>
              <tbody>
                {filtered.map((source) => (
                  <tr key={source.id} onClick={() => setSelected(source)}>
                    <td><strong>{source.name}</strong><span>{source.id}</span></td>
                    <td>{channelLabel(source.channel)}</td>
                    <td><strong>{sourceGroupLabel(source.sourceGroup)}</strong><span>{sourceTypeLabel(source.sourceType)} · {collectionStatusLabel(source.collectionStatus)}</span></td>
                    <td>{source.tier}</td>
                    <td>{adapterLabel(source.fetchAdapter)}</td>
                    <td>{source.fetchIntervalMinutes} 分钟</td>
                    <td>{visibilityLabel(source.visibility)}</td>
                    <td><StatusLabel value={source.enabled ? "enabled" : "disabled"} /></td>
                    <td>
                      <button className={source.enabled ? "danger ghost" : "primary"} onClick={(event) => { event.stopPropagation(); void toggle(source); }}>
                        {source.enabled ? <PowerOff size={15} /> : <Power size={15} />}
                        {source.enabled ? "停用" : "启用"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        </Section>
        <Section title="信源墙视图" description="公开前台展示的信源贡献卡片，包含编号、来源类型、接入状态和免费可读状态。">
          <div className="admin-source-wall">
            {filtered.map((source) => (
              <article key={source.id}>
                <div><strong>信源：{source.name}</strong><span>{formatContributorNo(source.contributorNo)}</span></div>
                <p>{source.socialHandle ? `${source.socialHandle} · ` : ""}{sourceGroupLabel(source.sourceGroup)} · {sourceTypeLabel(source.sourceType)}</p>
                <span>{source.tier}</span>
                <span>{collectionStatusLabel(source.collectionStatus)}</span>
                <span>{source.freeAccess ? "免费可读" : "需授权"}</span>
              </article>
            ))}
          </div>
        </Section>
      </div>
      <Section title="新增/编辑信源" description={selected ? `当前查看：${selected.name}` : "新增信源会直接写入生产信源表。"}>
        {selected && <p className="hint">URL：{selected.url}</p>}
        <div className="form-grid">
          <label>信源 ID<input value={form.id} onChange={(event) => setForm({ ...form, id: event.target.value })} /></label>
          <label>名称<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
          <label>URL<input value={form.url} onChange={(event) => setForm({ ...form, url: event.target.value })} /></label>
          <label>频道<select value={form.channel} onChange={(event) => setForm({ ...form, channel: event.target.value })}><option value="ai">AI 热点</option><option value="amazon">Amazon 情报</option></select></label>
          <label>等级<select value={form.tier} onChange={(event) => setForm({ ...form, tier: event.target.value })}><option value="T1">T1</option><option value="T1.5">T1.5</option><option value="T2">T2</option><option value="T3">T3</option></select></label>
          <label>间隔分钟<input value={form.fetchIntervalMinutes} onChange={(event) => setForm({ ...form, fetchIntervalMinutes: Number(event.target.value) })} /></label>
          <label>信源分组<select value={form.sourceGroup} onChange={(event) => setForm({ ...form, sourceGroup: event.target.value })}><option value="official">官方</option><option value="first_party">一手信源</option><option value="media">资讯</option><option value="social">推文</option><option value="community">社区</option><option value="vendor">服务商</option></select></label>
          <label>收集状态<select value={form.collectionStatus} onChange={(event) => setForm({ ...form, collectionStatus: event.target.value })}><option value="collectable">可抓取</option><option value="pending_api">待接入</option><option value="rate_limited">限流</option><option value="unavailable">不可用</option></select></label>
          <label>贡献编号<input value={form.contributorNo ?? ""} onChange={(event) => setForm({ ...form, contributorNo: event.target.value })} /></label>
          <label>社媒账号<input value={form.socialHandle ?? ""} onChange={(event) => setForm({ ...form, socialHandle: event.target.value })} /></label>
        </div>
        <button className="primary" onClick={submit}>保存信源</button>
      </Section>
    </div>
  );
}

function formatContributorNo(value?: string | null) {
  if (!value) return "未编号";
  const parts = value.split("-");
  if (parts.length === 2) return `${parts[0]} · ${parts[1]}`;
  return value;
}
