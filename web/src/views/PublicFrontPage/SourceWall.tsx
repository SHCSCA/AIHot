import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  ChevronDown,
  CircleCheck,
  CircleOff,
  ExternalLink,
  Globe2,
  LockKeyhole,
  RefreshCw
} from "lucide-react";
import { PaginationBar } from "../../components/PaginationBar";
import { useAsyncData } from "../../hooks";
import type { PublicApi } from "../../api";
import type { Source } from "../../types";
import {
  categoryLabel,
  collectionStatusLabel,
  fetchAdapterLabel,
  sourceGroupLabel,
  sourceTypeLabel
} from "../../labels";
import "../../styles/source-directory.css";

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
  const [expandedSourceKey, setExpandedSourceKey] = useState<string | null>(null);
  const [listHasEntered, setListHasEntered] = useState(false);
  const prefersReducedMotion = useReducedMotion();

  useEffect(() => {
    setPage(1);
    setExpandedSourceKey(null);
  }, [channel, q, sourceGroup]);

  useEffect(() => {
    setExpandedSourceKey(null);
  }, [page]);

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

  const activeGroupLabel = sourceGroups.find((item) => item.value === sourceGroup)?.label ?? "全部信源";
  const visibleSources = loading || error ? [] : sourcePage.items;
  const hasSources = visibleSources.length > 0;
  const visibleTotal = loading ? "…" : error ? 0 : (sourcePage.total ?? sourcePage.count);

  return (
    <section className="source-directory" aria-labelledby="source-directory-title" aria-busy={loading}>
      <div className="source-directory__head">
        <div>
          <h2 id="source-directory-title">可信信源档案</h2>
          <p>按层级扫描覆盖范围、访问条件与采集状态，需要时再展开质量和解析细节。</p>
        </div>
        <motion.button className="source-directory__refresh" type="button" onClick={reload}>
          <RefreshCw size={15} aria-hidden="true" />
          <span>刷新</span>
        </motion.button>
      </div>

      <div className="source-directory__filters" role="group" aria-label="信源类型筛选">
        {sourceGroups.map((option) => {
          const active = sourceGroup === option.value;
          return (
            <motion.button
              key={option.value || "all"}
              type="button"
              className={active ? "active" : ""}
              aria-pressed={active}
              onClick={() => setSourceGroup(option.value)}
            >
              {active && (
                <motion.span
                  className="source-directory__filter-active"
                  layoutId="source-directory-filter-active"
                  transition={prefersReducedMotion
                    ? { duration: 0 }
                    : { type: "spring", stiffness: 520, damping: 38, mass: 0.65 }}
                  aria-hidden="true"
                />
              )}
              <span className="source-directory__filter-label">{option.label}</span>
            </motion.button>
          );
        })}
      </div>

      <dl className="source-directory__summary" aria-label="当前信源筛选概览">
        <div>
          <dt>当前范围</dt>
          <dd>{activeGroupLabel}</dd>
        </div>
        <div>
          <dt>匹配信源</dt>
          <dd>{visibleTotal}</dd>
        </div>
        <div>
          <dt>本页展示</dt>
          <dd>{visibleSources.length}</dd>
        </div>
      </dl>

      {error && <p className="source-directory__feedback source-directory__feedback--error" role="alert">{error}</p>}
      {loading && <p className="source-directory__feedback" role="status" aria-live="polite">正在加载信源...</p>}
      {!loading && !error && !hasSources && (
        <div className="source-directory__empty" role="status">
          <strong>暂无匹配信源</strong>
          <span>当前筛选范围内还没有可展示的记录。</span>
        </div>
      )}

      {hasSources && (
        <motion.ul
          className="source-directory__list"
          aria-label="信源目录列表"
          initial={listHasEntered || prefersReducedMotion ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.24, ease: [0.2, 0, 0, 1] }}
          onAnimationComplete={() => setListHasEntered(true)}
        >
          {visibleSources.map((source, index) => {
            const sourceKey = `${page}-${index}-${source.name}`;
            const expanded = expandedSourceKey === sourceKey;
            const detailId = `source-profile-${page}-${index}`;
            const nameId = `source-name-${page}-${index}`;

            return (
              <li key={sourceKey} className="source-directory__item">
                <article aria-labelledby={nameId}>
                  <div className="source-directory__row">
                    <div className="source-directory__identity">
                      <div className="source-directory__name-line">
                        <h3 id={nameId}>{source.name || "未命名信源"}</h3>
                        <span className={tierClass(source.tier)}>{formatTier(source.tier)}</span>
                      </div>
                      {source.socialHandle && <p>{source.socialHandle}</p>}
                    </div>

                    <dl className="source-directory__cell">
                      <dt>类型 / 分组</dt>
                      <dd>{sourceTypeLabel(source.sourceType)} / {sourceGroupLabel(source.sourceGroup)}</dd>
                    </dl>

                    <dl className="source-directory__cell">
                      <dt>地区 / 语言</dt>
                      <dd>{formatText(source.region)} / {formatText(source.language)}</dd>
                    </dl>

                    <div className="source-directory__states" aria-label="访问和启用状态">
                      <div>
                        <span className="source-directory__state" data-tone={source.freeAccess ? "success" : "warning"}>
                          {source.freeAccess
                            ? <Globe2 size={13} aria-hidden="true" />
                            : <LockKeyhole size={13} aria-hidden="true" />}
                          {source.freeAccess ? "免费访问" : "需授权"}
                        </span>
                        <span className="source-directory__state" data-tone={source.enabled ? "success" : "muted"}>
                          {source.enabled
                            ? <CircleCheck size={13} aria-hidden="true" />
                            : <CircleOff size={13} aria-hidden="true" />}
                          {source.enabled ? "已启用" : "未启用"}
                        </span>
                      </div>
                      <small>{collectionStatusLabel(source.collectionStatus)}</small>
                    </div>

                    <button
                      className="source-directory__profile-toggle"
                      type="button"
                      onClick={() => setExpandedSourceKey(expanded ? null : sourceKey)}
                      aria-expanded={expanded}
                      aria-controls={detailId}
                    >
                      <span>{expanded ? "收起档案" : "查看档案"}</span>
                      <motion.span
                        className="source-directory__toggle-icon"
                        animate={{ rotate: expanded ? 180 : 0 }}
                        transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.18 }}
                        aria-hidden="true"
                      >
                        <ChevronDown size={15} />
                      </motion.span>
                    </button>
                  </div>

                  <AnimatePresence initial={false}>
                    {expanded && (
                      <motion.div
                        id={detailId}
                        className="source-directory__profile-shell"
                        role="region"
                        aria-labelledby={nameId}
                        initial={prefersReducedMotion ? false : { height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.22, ease: [0.2, 0, 0, 1] }}
                      >
                        <div className="source-directory__profile">
                          <div className="source-directory__profile-grid">
                            <section className="source-directory__profile-section" aria-label="质量档案">
                              <h4>质量档案</h4>
                              <dl>
                                <ProfileField label="权威权重" value={formatNumber(source.authorityWeight)} />
                                <ProfileField label="噪声水平" value={formatNoise(source.noiseLevel)} />
                              </dl>
                            </section>

                            <section className="source-directory__profile-section" aria-label="采集档案">
                              <h4>采集档案</h4>
                              <dl>
                                <ProfileField label="采集状态" value={collectionStatusLabel(source.collectionStatus)} />
                                <ProfileField label="采集频率" value={formatInterval(source.fetchIntervalMinutes)} />
                                <ProfileField label="采集适配器" value={fetchAdapterLabel(source.fetchAdapter)} />
                                <ProfileField label="解析类型" value={formatText(source.parserType)} />
                              </dl>
                            </section>

                            <section className="source-directory__profile-section" aria-label="标识档案">
                              <h4>标识档案</h4>
                              <dl>
                                <ProfileField label="贡献编号" value={formatContributorNo(source.contributorNo)} />
                                <ProfileField label="社媒账号" value={formatText(source.socialHandle)} />
                                <ProfileField label="默认分类" value={formatCategories(source.defaultCategories)} />
                              </dl>
                            </section>
                          </div>

                          <div className="source-directory__profile-foot">
                            <div className="source-directory__notes">
                              <strong>备注</strong>
                              <p>{formatText(source.notes)}</p>
                            </div>
                            <div className="source-directory__address">
                              <strong>信源地址</strong>
                              {source.url ? (
                                <a href={source.url} target="_blank" rel="noreferrer">
                                  <span>{source.url}</span>
                                  <ExternalLink size={14} aria-hidden="true" />
                                </a>
                              ) : (
                                <span>--</span>
                              )}
                            </div>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </article>
              </li>
            );
          })}
        </motion.ul>
      )}

      <PaginationBar
        page={page}
        totalPages={sourcePage.totalPages ?? 1}
        onPageChange={setPage}
        disabled={loading}
      />
    </section>
  );
}

function ProfileField({ label, value }: { label: string; value: string }) {
  return (
    <div className="source-directory__profile-field">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function formatContributorNo(value?: string | null) {
  if (!value) return "--";
  const parts = value.split("-");
  if (parts.length === 2) return `${parts[0]} · ${parts[1]}`;
  return value;
}

function formatNoise(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${Math.round(value * 100)}%`;
}

function formatNumber(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${Math.round(value)}`;
}

function formatInterval(value?: number | null) {
  if (!value) return "手动";
  if (value < 60) return `${value} 分钟`;
  const hours = value / 60;
  return Number.isInteger(hours) ? `${hours} 小时` : `${hours.toFixed(1)} 小时`;
}

function formatText(value?: string | null) {
  return value?.trim() || "--";
}

function formatCategories(values?: string[] | null) {
  if (!values?.length) return "--";
  return values.map((value) => categoryLabel(value)).join("、");
}

function formatTier(tier?: string | null) {
  return tier?.trim().toUpperCase() || "未分级";
}

function tierClass(tier?: string | null) {
  const normalized = (tier ?? "").toLowerCase();
  if (normalized === "t1") return "source-directory__tier source-directory__tier--t1";
  if (normalized === "t2") return "source-directory__tier source-directory__tier--t2";
  if (normalized === "t3") return "source-directory__tier source-directory__tier--t3";
  return "source-directory__tier";
}
