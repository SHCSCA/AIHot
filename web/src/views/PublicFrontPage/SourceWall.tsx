import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ExternalLink, RefreshCw } from "lucide-react";
import { PaginationBar } from "../../components/PaginationBar";
import { useAsyncData } from "../../hooks";
import type { PublicApi } from "../../api";
import type { Source } from "../../types";
import { sourceGroupLabel, sourceTypeLabel, collectionStatusLabel } from "../../labels";

interface SourceWallProps {
  api: PublicApi;
  channel: string;
  q?: string;
}

const SOURCE_PAGE_SIZE = 6;

const sourceGroups = [
  { value: "", label: "全部信源" },
  { value: "official,first_party", label: "官方/一手" },
  { value: "media", label: "资讯" },
  { value: "social,community", label: "社媒/社区" }
];

export function SourceWall({ api, channel, q }: SourceWallProps) {
  const [page, setPage] = useState(1);
  const [sourceGroup, setSourceGroup] = useState("");

  useEffect(() => {
    setPage(1);
  }, [channel, q, sourceGroup]);

  const { data: sourcePage, error, loading, reload } = useAsyncData(
    async () => {
      if (typeof api.listSourcesPage === "function") {
        return api.listSourcesPage({ channel, q, sourceGroup, page, pageSize: SOURCE_PAGE_SIZE });
      }
      const sources = await api.listSources({ channel, sourceGroup });
      return {
        items: sources,
        count: sources.length,
        page: 1,
        pageSize: SOURCE_PAGE_SIZE,
        total: sources.length,
        totalPages: 1,
        hasNext: false,
        nextCursor: null
      };
    },
    { items: [] as Source[], count: 0, page: 1, pageSize: SOURCE_PAGE_SIZE, total: 0, totalPages: 1, hasNext: false, nextCursor: null },
    [api, channel, page, q, sourceGroup]
  );

  return (
    <section className="source-wall">
      <div className="source-wall-head">
        <div>
          <h2>信源墙</h2>
          <p>把公开信源按权威性、可采集性和噪声风险分层展示。贡献编号保留，但核心是判断这个来源为什么值得进入情报池。</p>
        </div>
        <motion.button
          className="ghost dark"
          onClick={reload}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          <RefreshCw size={15} />刷新
        </motion.button>
      </div>

      <div className="segmented-row source-tabs" aria-label="信源墙类型筛选">
        {sourceGroups.map((option) => (
          <motion.button
            key={option.value || "all"}
            className={sourceGroup === option.value ? "active" : ""}
            onClick={() => setSourceGroup(option.value)}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            {option.label}
          </motion.button>
        ))}
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p className="hint">正在加载信源...</p>}

      <div className="source-wall-summary" aria-label="当前信源筛选概览">
        <span><small>当前范围</small><strong>{sourceGroup ? sourceGroups.find((item) => item.value === sourceGroup)?.label : "全部信源"}</strong></span>
        <span><small>匹配信源</small><strong>{sourcePage.total ?? sourcePage.count}</strong></span>
        <span><small>本页展示</small><strong>{sourcePage.items.length}</strong></span>
      </div>

      <div className="source-wall-grid">
        {sourcePage.items.map((source) => (
          <motion.article
            key={source.id}
            className="source-wall-card liquid-glass-subtle"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <div className="source-card-top">
              <div>
                <h3>{source.name || "未命名信源"}</h3>
                <p>{source.socialHandle ? `${source.socialHandle} · ` : ""}{sourceTypeLabel(source.sourceType)} · {sourceGroupLabel(source.sourceGroup)}</p>
              </div>
              <span className={tierClass(source.tier)}>{source.tier || "未分级"}</span>
            </div>
            <div className="source-trust-grid" aria-label={`${source.name} 信源档案`}>
              <span><small>权威权重</small><strong>{Math.round(source.authorityWeight ?? 0)}</strong></span>
              <span><small>噪声风险</small><strong>{formatNoise(source.noiseLevel)}</strong></span>
              <span><small>采集频率</small><strong>{formatInterval(source.fetchIntervalMinutes)}</strong></span>
            </div>
            <div className="source-card-meta" aria-label="信源状态">
              <span>{collectionStatusLabel(source.collectionStatus)}</span>
              <span>{source.freeAccess ? "免费可读" : "需授权"}</span>
              <span>{source.enabled ? "已启用" : "未启用"}</span>
              <span>{formatContributorNo(source.contributorNo)}</span>
            </div>
            {source.url && (
              <a className="source-card-link" href={source.url} target="_blank" rel="noreferrer">
                <ExternalLink size={14} />查看信源
              </a>
            )}
          </motion.article>
        ))}
      </div>

      <PaginationBar
        page={page}
        totalPages={sourcePage.totalPages ?? 1}
        onPageChange={setPage}
        disabled={loading}
      />
    </section>
  );
}

function formatContributorNo(value?: string | null) {
  if (!value) return "AIHOT · --";
  const parts = value.split("-");
  if (parts.length === 2) return `${parts[0]} · ${parts[1]}`;
  return value;
}

function formatNoise(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${Math.round(value * 100)}%`;
}

function formatInterval(value?: number | null) {
  if (!value) return "手动";
  if (value < 60) return `${value} 分钟`;
  const hours = value / 60;
  return Number.isInteger(hours) ? `${hours} 小时` : `${hours.toFixed(1)} 小时`;
}

function tierClass(tier?: string | null) {
  const normalized = (tier ?? "").toLowerCase();
  if (normalized === "t1") return "source-tier source-tier-1";
  if (normalized === "t2") return "source-tier source-tier-2";
  return "source-tier";
}
