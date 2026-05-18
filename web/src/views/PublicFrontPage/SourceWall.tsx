import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { RefreshCw } from "lucide-react";
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
          <p>每张卡片都是一位贡献者的功劳；审核通过的提报会获得专属编号，永久收录在这里。</p>
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

      <div className="source-wall-grid">
        {sourcePage.items.map((source) => (
          <motion.article
            key={source.id}
            className="source-wall-card glass"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <div className="source-card-top">
              <h3>{source.name}</h3>
              <span>{formatContributorNo(source.contributorNo)}</span>
            </div>
            <p>{source.socialHandle ? `${source.socialHandle} · ` : ""}{sourceTypeLabel(source.sourceType)} · {sourceGroupLabel(source.sourceGroup)}</p>
            <div className="source-card-meta">
              <span>{source.tier}</span>
              <span>{collectionStatusLabel(source.collectionStatus)}</span>
              <span>{source.freeAccess ? "免费可读" : "需授权"}</span>
            </div>
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