import { Eye, Power, PowerOff, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { AdminApi } from "../api";
import { AdminChannelCards, type AdminChannel, usePersistedAdminChannel } from "../components/AdminChannelCards";
import { MetricCard, MetricGrid } from "../components/MetricCard";
import { PaginationBar } from "../components/PaginationBar";
import { Section, TableWrap } from "../components/Section";
import { StatusLabel } from "../components/StatusLabel";
import { collectionStatusLabel, sourceGroupLabel, sourceTypeLabel } from "../labels";
import type { Page, Source } from "../types";
import { adapterLabel, channelLabel, formatPercent, visibilityLabel } from "../utils";

const TABLE_PAGE_SIZE = 50;
const WALL_PAGE_SIZE = 6;

const emptyPage: Page<Source> = {
  items: [],
  count: 0,
  page: 1,
  pageSize: TABLE_PAGE_SIZE,
  total: 0,
  totalPages: 1,
  hasNext: false,
  nextCursor: null,
  metrics: {}
};

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
  enabled: true,
  visibility: "public",
  sourceGroup: "media",
  contributorNo: "",
  socialHandle: "",
  collectionStatus: "collectable",
  freeAccess: true,
  notes: ""
};

type SourceFilters = {
  q: string;
  sourceGroup: string;
  collectionStatus: string;
  enabled: string;
};

export function SourcesView({ api }: { api: AdminApi }) {
  const [channel, setChannel] = usePersistedAdminChannel("admin-sources-channel");
  const [filters, setFilters] = useState<SourceFilters>({ q: "", sourceGroup: "", collectionStatus: "", enabled: "" });
  const [sourcePage, setSourcePage] = useState<Page<Source>>(emptyPage);
  const [wallPageData, setWallPageData] = useState<Page<Source>>({ ...emptyPage, pageSize: WALL_PAGE_SIZE });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [wallPage, setWallPage] = useState(1);
  const [selected, setSelected] = useState<Source | null>(null);
  const [form, setForm] = useState<Source>({ ...newSource, channel });
  const [formMessage, setFormMessage] = useState<{ tone: "info" | "success" | "error"; text: string } | null>(null);
  const [toggleMessage, setToggleMessage] = useState<{ sourceId: string; tone: "info" | "success" | "error"; text: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [invalidFields, setInvalidFields] = useState<string[]>([]);
  const idInputRef = useRef<HTMLInputElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const urlInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setPage(1);
    setWallPage(1);
    setForm((current) => ({ ...current, channel }));
  }, [channel, filters.q, filters.sourceGroup, filters.collectionStatus, filters.enabled]);

  useEffect(() => {
    void loadTable(page);
  }, [api, channel, filters.q, filters.sourceGroup, filters.collectionStatus, filters.enabled, page]);

  useEffect(() => {
    void loadWall(wallPage);
  }, [api, channel, filters.q, filters.sourceGroup, filters.collectionStatus, filters.enabled, wallPage]);

  async function loadTable(pageNumber = 1) {
    setLoading(true);
    try {
      const nextPage = await api.listSourcesPage({ ...apiFilters(channel, filters), page: pageNumber, pageSize: TABLE_PAGE_SIZE });
      setSourcePage(nextPage);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "信源加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadWall(pageNumber = 1) {
    try {
      const nextPage = await api.listSourcesPage({ ...apiFilters(channel, filters), page: pageNumber, pageSize: WALL_PAGE_SIZE });
      setWallPageData(nextPage);
    } catch (err) {
      setError(err instanceof Error ? err.message : "信源目录加载失败");
    }
  }

  async function toggle(source: Source) {
    const nextEnabled = !source.enabled;
    setToggleMessage({ sourceId: source.id, tone: "info", text: `${sourceDisplayName(source)} 正在${nextEnabled ? "启用" : "停用"}...` });
    try {
      await api.patchSource(source.id, { enabled: nextEnabled });
      setToggleMessage({ sourceId: source.id, tone: "success", text: `${sourceDisplayName(source)} 已${nextEnabled ? "启用" : "停用"}。` });
      await loadTable(page);
      await loadWall(wallPage);
    } catch (err) {
      setToggleMessage({ sourceId: source.id, tone: "error", text: err instanceof Error ? err.message : "信源启停失败。" });
    }
  }

  async function submit() {
    const payload = { ...form, id: form.id.trim(), name: form.name.trim(), url: form.url.trim() };
    const missingFields = [
      !payload.id ? "id" : null,
      !payload.name ? "name" : null,
      !payload.url ? "url" : null
    ].filter((field): field is string => field !== null);
    setInvalidFields(missingFields);
    if (missingFields.length > 0) {
      setFormMessage({ tone: "error", text: "信源 ID、名称和 URL 不能为空。" });
      const fieldRefs = { id: idInputRef, name: nameInputRef, url: urlInputRef };
      fieldRefs[missingFields[0] as keyof typeof fieldRefs].current?.focus();
      return;
    }
    setSubmitting(true);
    setFormMessage({ tone: "info", text: "正在测试信源连通性..." });
    try {
      await api.createSource(payload);
      setForm({ ...newSource, channel });
      setInvalidFields([]);
      setFormMessage({ tone: "success", text: "信源已保存，连通性测试通过。" });
      setPage(1);
      setWallPage(1);
      await loadTable(1);
      await loadWall(1);
    } catch (err) {
      setFormMessage({ tone: "error", text: err instanceof Error ? err.message : "信源保存失败。" });
    } finally {
      setSubmitting(false);
    }
  }

  const metrics = sourcePage.metrics ?? {};
  const channelMetrics = [
    { channel: "ai", metrics: channel === "ai" ? metrics : {} },
    { channel: "amazon", metrics: channel === "amazon" ? metrics : {} }
  ];

  return (
    <div className="view-stack split-layout">
      <div className="view-stack">
        <AdminChannelCards value={channel} onChange={setChannel} metrics={channelMetrics} />
        <MetricGrid>
          <MetricCard label="信源总数" value={metrics.sourceCount ?? sourcePage.total ?? 0} />
          <MetricCard label="已启用" value={metrics.enabledSourceCount ?? 0} tone="good" />
          <MetricCard label="高权威源" value={metrics.highAuthorityCount ?? 0} />
          <MetricCard label="待接入社媒" value={metrics.pendingSocialCount ?? 0} tone="warn" />
        </MetricGrid>
        <Section
          title="信源列表"
          description={`当前显示 ${channelLabel(channel)}，共 ${sourcePage.total ?? 0} 条匹配结果。`}
          error={error}
        >
          <SourceFilterPanel filters={filters} onChange={(next) => setFilters({ ...filters, ...next })} />
          {toggleMessage && (
            <p
              className={`form-message ${toggleMessage.tone}`}
              role={toggleMessage.tone === "error" ? "alert" : "status"}
              aria-live={toggleMessage.tone === "error" ? "assertive" : "polite"}
            >
              {toggleMessage.text}
            </p>
          )}
          <TableWrap>
            <table>
              <thead><tr><th>信源</th><th>运行状态</th><th>健康/收集</th><th>权重</th><th>抓取方式</th><th>状态</th><th>操作</th></tr></thead>
              <tbody>
                {sourcePage.items.map((source, index) => (
                  <tr key={source.id || `empty-${index}`}>
                    <td>
                      <strong>{sourceDisplayName(source)}</strong>
                      <span>{sourceDisplayId(source)}</span>
                      <span>{channelLabel(source.channel)} · {source.tier}</span>
                    </td>
                    <td>
                      <StatusLabel value={source.enabled ? "enabled" : "disabled"} />
                      <span>{source.enabled ? "参与抓取调度" : "暂停调度"} · {visibilityLabel(source.visibility)}</span>
                    </td>
                    <td>
                      <span className={`status ${collectionStatusClass(source.collectionStatus)}`}>
                        {collectionStatusLabel(source.collectionStatus)}
                      </span>
                      <span>{sourceGroupLabel(source.sourceGroup)} · {sourceTypeLabel(source.sourceType)} · 发布方 {formatPublisherKey(source.publisherKey)}</span>
                      <span>{source.freeAccess === false ? "需授权" : "免费可读"}</span>
                    </td>
                    <td>
                      <strong>{source.authorityWeight}</strong>
                      <span>噪声 {formatPercent(source.noiseLevel ?? 0)}</span>
                    </td>
                    <td>
                      <strong>{adapterLabel(source.fetchAdapter)}</strong>
                      <span>{source.parserType || "默认解析"} · 全局每 {formatInterval(source.fetchIntervalMinutes)}抓取</span>
                    </td>
                    <td>
                      <strong>{source.collectionStatus ? collectionStatusLabel(source.collectionStatus) : "未设置"}</strong>
                      <span>{source.notes?.trim() || "无备注"}</span>
                    </td>
                    <td>
                      <div className="inline-actions">
                        <button className="ghost" type="button" onClick={() => setSelected(source)} aria-label={`查看信源 ${sourceDisplayName(source)}`}>
                          <Eye size={15} />查看
                        </button>
                        <button
                          className={source.enabled ? "danger ghost" : "primary"}
                          disabled={toggleMessage?.sourceId === source.id && toggleMessage.tone === "info"}
                          aria-label={`${toggleMessage?.sourceId === source.id && toggleMessage.tone === "info" ? "正在处理" : source.enabled ? "停用" : "启用"}信源 ${sourceDisplayName(source)}`}
                          onClick={() => { void toggle(source); }}
                        >
                          {source.enabled ? <PowerOff size={15} /> : <Power size={15} />}
                          {toggleMessage?.sourceId === source.id && toggleMessage.tone === "info" ? "处理中..." : source.enabled ? "停用" : "启用"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
          <PaginationBar page={page} totalPages={sourcePage.totalPages ?? 1} onPageChange={setPage} disabled={loading} />
        </Section>
        <Section title="信源目录视图" description="公开前台展示的信源目录，固定 6 条一页，跟随当前频道和筛选条件。">
          <div className="admin-source-wall">
            {wallPageData.items.map((source, index) => (
              <article key={source.id || `wall-empty-${index}`}>
                <div><strong>{sourceDisplayName(source)}</strong><span>{formatContributorNo(source.contributorNo)}</span></div>
                <p>{source.socialHandle ? `${source.socialHandle} · ` : ""}{sourceGroupLabel(source.sourceGroup)} · {sourceTypeLabel(source.sourceType)}</p>
                <span>{source.tier}</span>
                <span>{collectionStatusLabel(source.collectionStatus)}</span>
                <span>{source.freeAccess ? "免费可读" : "需授权"}</span>
              </article>
            ))}
          </div>
          <PaginationBar page={wallPage} totalPages={wallPageData.totalPages ?? 1} onPageChange={setWallPage} disabled={loading} />
        </Section>
      </div>
      <Section title="新增信源" description={selected ? `当前查看：${sourceDisplayName(selected)}` : `新增信源会写入 ${channelLabel(channel)}，保存前会检测重复并抓取一次；采集周期统一继承全局策略。`}>
        {selected && <p className="hint" role="status" aria-live="polite">已选择信源 {sourceDisplayName(selected)}。URL：{selected.url || "缺少 URL"}</p>}
        <div className="form-grid">
          <label>信源 ID<input ref={idInputRef} value={form.id} aria-invalid={invalidFields.includes("id")} aria-describedby={invalidFields.includes("id") ? "source-form-message" : undefined} onChange={(event) => { setForm({ ...form, id: event.target.value }); setInvalidFields((current) => current.filter((field) => field !== "id")); }} /></label>
          <label>名称<input ref={nameInputRef} value={form.name} aria-invalid={invalidFields.includes("name")} aria-describedby={invalidFields.includes("name") ? "source-form-message" : undefined} onChange={(event) => { setForm({ ...form, name: event.target.value }); setInvalidFields((current) => current.filter((field) => field !== "name")); }} /></label>
          <label>URL<input ref={urlInputRef} value={form.url} aria-invalid={invalidFields.includes("url")} aria-describedby={invalidFields.includes("url") ? "source-form-message" : undefined} onChange={(event) => { setForm({ ...form, url: event.target.value }); setInvalidFields((current) => current.filter((field) => field !== "url")); }} /></label>
          <label>频道<select value={form.channel} onChange={(event) => setForm({ ...form, channel: event.target.value })}><option value="ai">AI 热点</option><option value="amazon">Amazon 情报</option></select></label>
          <label>等级<select value={form.tier} onChange={(event) => setForm({ ...form, tier: event.target.value })}><option value="T1">T1</option><option value="T1.5">T1.5</option><option value="T2">T2</option><option value="T3">T3</option></select></label>
          <label>采集周期<output className="source-policy-output" aria-describedby="global-source-interval">全局统一策略</output></label>
          <label>信源分组<select value={form.sourceGroup} onChange={(event) => setForm({ ...form, sourceGroup: event.target.value })}><option value="official">官方</option><option value="first_party">一手信源</option><option value="media">资讯</option><option value="social">推文</option><option value="community">社区</option><option value="vendor">服务商</option></select></label>
          <label>收集状态<select value={form.collectionStatus} onChange={(event) => setForm({ ...form, collectionStatus: event.target.value })}><option value="collectable">可抓取</option><option value="pending_api">待接入</option><option value="rate_limited">限流</option><option value="unavailable">不可用</option></select></label>
          <label>贡献编号<input value={form.contributorNo ?? ""} onChange={(event) => setForm({ ...form, contributorNo: event.target.value })} /></label>
          <label>社媒账号<input value={form.socialHandle ?? ""} onChange={(event) => setForm({ ...form, socialHandle: event.target.value })} /></label>
        </div>
        <p id="global-source-interval" className="hint">周期只在全局采集策略中维护，新增或启停信源无需逐条设置。</p>
        {formMessage && (
          <p
            id="source-form-message"
            className={`form-message ${formMessage.tone}`}
            role={formMessage.tone === "error" ? "alert" : "status"}
            aria-live={formMessage.tone === "error" ? "assertive" : "polite"}
          >
            {formMessage.text}
          </p>
        )}
        <button className="primary" onClick={submit} disabled={submitting}>{submitting ? "测试中..." : "保存并测试信源"}</button>
      </Section>
    </div>
  );
}

function SourceFilterPanel({ filters, onChange }: { filters: SourceFilters; onChange: (filters: Partial<SourceFilters>) => void }) {
  return (
    <div className="admin-filter-panel">
      <label className="admin-search"><Search size={16} /><input aria-label="搜索信源" placeholder="搜索名称 / ID / URL" value={filters.q} onChange={(event) => onChange({ q: event.target.value })} /></label>
      <label>信源类型<select aria-label="信源类型" value={filters.sourceGroup} onChange={(event) => onChange({ sourceGroup: event.target.value })}><option value="">全部类型</option><option value="official,first_party">官方/一手</option><option value="media">资讯</option><option value="social,community">社媒/社区</option><option value="vendor">服务商</option></select></label>
      <label>收集状态<select aria-label="收集状态" value={filters.collectionStatus} onChange={(event) => onChange({ collectionStatus: event.target.value })}><option value="">全部状态</option><option value="collectable">可抓取</option><option value="pending_api">待接入</option><option value="rate_limited">限流</option><option value="unavailable">不可用</option></select></label>
      <label>启用状态<select aria-label="启用状态" value={filters.enabled} onChange={(event) => onChange({ enabled: event.target.value })}><option value="">全部</option><option value="true">启用</option><option value="false">停用</option></select></label>
    </div>
  );
}

function apiFilters(channel: AdminChannel, filters: SourceFilters) {
  return {
    channel,
    q: filters.q || undefined,
    sourceGroup: filters.sourceGroup || undefined,
    collectionStatus: filters.collectionStatus || undefined,
    enabled: filters.enabled || undefined
  };
}

function formatContributorNo(value?: string | null) {
  if (!value) return "未编号";
  const parts = value.split("-");
  if (parts.length === 2) return `${parts[0]} · ${parts[1]}`;
  return value;
}

function sourceDisplayName(source: Source) {
  return source.name?.trim() || "未命名信源";
}

function sourceDisplayId(source: Source) {
  return source.id?.trim() || "缺少信源 ID";
}

function collectionStatusClass(value?: string | null) {
  if (value === "collectable") return "status-enabled";
  if (value === "unavailable") return "status-failed";
  return "status-pending";
}

function formatPublisherKey(value?: string | null) {
  if (!value || value === "unknown") return "自动识别";
  return value.replace(/^(company|github_org|research):/, "");
}

function formatInterval(minutes?: number) {
  if (minutes == null) return "全局策略";
  if (minutes % 60 === 0) return `${minutes / 60} 小时`;
  return `${minutes} 分钟`;
}
