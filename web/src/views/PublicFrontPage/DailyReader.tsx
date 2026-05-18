import { motion, AnimatePresence } from "framer-motion";
import type { PublicApi } from "../../api";
import type { DailyArchiveItem, DailySection, PublicDaily } from "../../types";
import { channelLabel, categoryLabel } from "../../labels";
import { formatDateTime } from "../../utils";
import { ExternalLink } from "lucide-react";
import { useAsyncData } from "../../hooks";
import { useEffect, useState } from "react";

function today() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function dateParts(value: string) {
  const [year = 0, month = 1, day = 1] = value.split("-").map((part) => Number(part));
  return { year, month, day, date: new Date(year, month - 1, day) };
}

function dailyDateLabel(value: string) {
  const { year, month, day, date } = dateParts(value);
  const weekday = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"][date.getDay()];
  return `${year}年${month}月${day}日　${weekday}`;
}

function archiveMonthLabel(value: string) {
  const { year, month } = dateParts(value);
  return `${year} 年 ${month} 月`;
}

function dailySections(daily: PublicDaily | null): DailySection[] {
  if (!daily) return [];
  if (Array.isArray(daily.sections)) return daily.sections;
  const legacySections = daily.sectionsJson ?? daily.sections;
  const highlights = Array.isArray(legacySections?.highlights) ? legacySections.highlights : [];
  const items = highlights.filter((item): item is Record<string, string | number | null> => Boolean(item) && typeof item === "object");
  const grouped = new Map<string, DailySection>();
  items.forEach((item) => {
    const category = String(item.category || "industry");
    const section = grouped.get(category) ?? { category, label: categoryLabel(category), count: 0, items: [] };
    section.items.push({
      eventId: item.eventId ? String(item.eventId) : null,
      title: String(item.title || ""),
      summary: item.summary ? String(item.summary) : null,
      entryReason: item.entryReason ? String(item.entryReason) : null,
      category,
      score: Number(item.score || 0),
      lastSeenAt: item.lastSeenAt ? String(item.lastSeenAt) : null
    });
    section.count = section.items.length;
    grouped.set(category, section);
  });
  return [...grouped.values()];
}

function sectionEnglishLabel(category: string) {
  if (/ai_models|papers/.test(category)) return "MODEL RELEASES";
  if (/ai_products|agent_tools/.test(category)) return "PRODUCT & AGENTS";
  if (/industry|monetization/.test(category)) return "INDUSTRY SIGNALS";
  if (/policy|account|compliance/.test(category)) return "POLICY & ACCOUNT";
  if (/fba|logistics/.test(category)) return "FBA & LOGISTICS";
  if (/ads|listing/.test(category)) return "ADS & LISTING";
  if (/fees|product/.test(category)) return "MARGIN & SELECTION";
  return "DAILY BRIEF";
}

interface DailyReaderProps {
  api: PublicApi;
  channel: "ai" | "amazon";
  zenMode?: boolean;
}

export function DailyReader({ api, channel, zenMode = false }: DailyReaderProps) {
  const [date, setDate] = useState(today());
  const [entering, setEntering] = useState(zenMode);
  const [zenOpen, setZenOpen] = useState(zenMode);
  const { data: daily, error, loading, reload } = useAsyncData<PublicDaily | null>(
    () => api.getDaily({ channel, date }),
    null,
    [channel, date]
  );
  const { data: archive } = useAsyncData(
    () => api.listDailies({ channel, page: 1, pageSize: 20 }),
    { items: [] as DailyArchiveItem[], count: 0, page: 1, pageSize: 20, total: 0, totalPages: 1, hasNext: false, nextCursor: null },
    [api, channel]
  );
  const sections = dailySections(daily);
  const storyCount = daily?.stats?.storyCount ?? sections.reduce((sum, section) => sum + section.items.length, 0);
  const archiveBaseDate = archive.items[0]?.date ?? date;
  const latestArchiveDate = archive.items[0]?.date;

  useEffect(() => {
    if (zenMode) {
      setZenOpen(true);
      const t = setTimeout(() => setEntering(false), 50);
      return () => clearTimeout(t);
    }
  }, [zenMode]);

  useEffect(() => {
    if (loading || error || daily || !latestArchiveDate || latestArchiveDate === date) return;
    setDate(latestArchiveDate);
  }, [daily, date, error, latestArchiveDate, loading]);

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.06, delayChildren: 0.15 },
    },
    exit: { opacity: 0, transition: { duration: 0.25 } },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.5, ease: [0.4, 0, 0.2, 1] as [number, number, number, number] },
    },
  };

  const overlayVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { duration: 0.3 } },
    exit: { opacity: 0, transition: { duration: 0.3 } },
  };

  return (
    <AnimatePresence mode="wait">
      {zenOpen ? (
        <motion.div
          className="zen-overlay"
          aria-label="专注阅读模式"
          role="dialog"
          aria-modal="true"
          variants={overlayVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
        >
          <button className="zen-close" type="button" onClick={() => setZenOpen(false)}>退出专注</button>
          <motion.div
            className="zen-sidebar"
            initial={{ opacity: entering ? 0 : 0.2 }}
            animate={{ opacity: 0.2 }}
            transition={{ duration: 0.5 }}
          />

          <motion.article
            className="zen-document"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
          >
            {error && <p className="error">{error}</p>}
            {loading && !daily && <p className="hint">正在读取日报...</p>}
            {daily && (
              <>
                <motion.header className="daily-cover" variants={itemVariants}>
                  <p className="daily-volume">VOL.{daily.date.replaceAll("-", ".")} · {storyCount} STORIES · {channelLabel(daily.channel)} DAILY</p>
                  <h2>
                    <span className="daily-logo-ai">AI</span>
                    <span className="daily-logo-hot">HOT</span>
                    <span className="daily-logo-title">日报</span>
                  </h2>
                  <div className="daily-cover-meta">
                    <strong>{dailyDateLabel(daily.date)}</strong>
                    <i aria-hidden="true" />
                    <span>DAILY · 每早八时</span>
                    <button className="ghost dark" onClick={reload}>刷新日报</button>
                  </div>
                  <p className="daily-cover-summary">{daily.windowLabel || "基于最近 24 小时精选情报自动生成"}</p>
                </motion.header>

                {sections.length > 0 && (
                  <motion.nav className="daily-toc" aria-label="日报目录" variants={itemVariants}>
                    <strong>目录</strong>
                    {sections.map((section, sectionIndex) => (
                      <a key={section.category} href={`#daily-${section.category}`}>
                        {String(sectionIndex + 1).padStart(2, "0")} {section.label}<span>{section.count} 篇</span>
                      </a>
                    ))}
                  </motion.nav>
                )}

                {sections.length === 0 && <p className="hint">最近 24 小时暂无可发布精选情报。</p>}

                {sections.map((section, sectionIndex) => (
                  <motion.section
                    className="daily-section"
                    key={section.category}
                    id={`daily-${section.category}`}
                    variants={itemVariants}
                  >
                    <div className="daily-section-title">
                      <strong>{String(sectionIndex + 1).padStart(2, "0")}</strong>
                      <div>
                        <h3>{section.label}</h3>
                        <span>{sectionEnglishLabel(section.category)}</span>
                      </div>
                      <em>{section.count} 篇</em>
                    </div>
                    {section.items.map((item) => (
                      <motion.article
                        className="daily-story"
                        key={item.eventId || item.title}
                        variants={itemVariants}
                      >
                        <div className="daily-story-head">
                          <h4>{item.title}</h4>
                          {item.mainItem?.url && (
                            <a href={item.mainItem.url} target="_blank" rel="noreferrer">
                              <ExternalLink size={15} />原文
                            </a>
                          )}
                        </div>
                        <div className="daily-story-meta">
                          <span>{categoryLabel(item.category)}</span>
                          {item.mainItem?.sourceName && <span>{item.mainItem.sourceName}</span>}
                          <span>精选分 {Math.round(Number(item.score ?? 0))}</span>
                        </div>
                        <p>{item.summary || "待 AI 处理后生成中文摘要。"}</p>
                        {item.entryReason && <em>{item.entryReason}</em>}
                      </motion.article>
                    ))}
                  </motion.section>
                ))}
              </>
            )}
            {!loading && !daily && !error && (
              <section className="daily-document dark daily-empty">
                <p className="daily-volume">AIHOT DAILY</p>
                <h2>暂无日报</h2>
                <p className="daily-cover-summary">当前日期没有已发布日报，请从左侧归档选择其他日期，或稍后刷新。</p>
                <button className="ghost dark" onClick={reload}>刷新日报</button>
              </section>
            )}
          </motion.article>
        </motion.div>
      ) : (
        <motion.div
          className="daily-reader dark"
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
        >
          <motion.div className="daily-reader-actions" variants={itemVariants}>
            <button className="ghost dark" type="button" onClick={() => setZenOpen(true)}>专注阅读</button>
          </motion.div>
          <motion.aside className="daily-archive" variants={itemVariants}>
            <button className="latest" onClick={() => setDate(latestArchiveDate ?? today())}>
              <strong>最新一期</strong><span>{latestArchiveDate ?? today()}</span>
            </button>
            <div className="daily-archive-month">
              <span>{archiveMonthLabel(archiveBaseDate)}</span>
              <em>{archive.items.length}</em>
            </div>
            <div className="daily-archive-list">
              {archive.items.map((item) => (
                <button
                  key={item.id}
                  className={date === item.date ? "active" : ""}
                  onClick={() => setDate(item.date)}
                >
                  <strong>{item.date.slice(8)} 日</strong>
                  <span>{item.leadTitle || item.title}</span>
                </button>
              ))}
            </div>
          </motion.aside>

          <motion.div className="daily-document-wrap" variants={itemVariants}>
            {error && <p className="error">{error}</p>}
            {loading && !daily && <p className="hint">正在读取日报...</p>}
            {daily && (
              <motion.article className="daily-document dark" key={date}>
                <motion.header className="daily-cover" variants={itemVariants}>
                  <p className="daily-volume">VOL.{daily.date.replaceAll("-", ".")} · {storyCount} STORIES · {channelLabel(daily.channel)} DAILY</p>
                  <h2>
                    <span className="daily-logo-ai">AI</span>
                    <span className="daily-logo-hot">HOT</span>
                    <span className="daily-logo-title">日报</span>
                  </h2>
                  <div className="daily-cover-meta">
                    <strong>{dailyDateLabel(daily.date)}</strong>
                    <i aria-hidden="true" />
                    <span>DAILY · 每早八时</span>
                    <button className="ghost dark" onClick={reload}>刷新日报</button>
                  </div>
                  <p className="daily-cover-summary">{daily.windowLabel || "基于最近 24 小时精选情报自动生成"}</p>
                </motion.header>

                {sections.length > 0 && (
                  <motion.nav className="daily-toc" aria-label="日报目录" variants={itemVariants}>
                    <strong>目录</strong>
                    {sections.map((section, sectionIndex) => (
                      <a key={section.category} href={`#daily-${section.category}`}>
                        {String(sectionIndex + 1).padStart(2, "0")} {section.label}<span>{section.count} 篇</span>
                      </a>
                    ))}
                  </motion.nav>
                )}

                {sections.length === 0 && <p className="hint">最近 24 小时暂无可发布精选情报。</p>}

                {sections.map((section, sectionIndex) => (
                  <motion.section
                    className="daily-section"
                    key={section.category}
                    id={`daily-${section.category}`}
                    variants={itemVariants}
                  >
                    <div className="daily-section-title">
                      <strong>{String(sectionIndex + 1).padStart(2, "0")}</strong>
                      <div>
                        <h3>{section.label}</h3>
                        <span>{sectionEnglishLabel(section.category)}</span>
                      </div>
                      <em>{section.count} 篇</em>
                    </div>
                    {section.items.map((item) => (
                      <motion.article
                        className="daily-story"
                        key={item.eventId || item.title}
                        variants={itemVariants}
                      >
                        <div className="daily-story-head">
                          <h4>{item.title}</h4>
                          {item.mainItem?.url && (
                            <a href={item.mainItem.url} target="_blank" rel="noreferrer">
                              <ExternalLink size={15} />原文
                            </a>
                          )}
                        </div>
                        <div className="daily-story-meta">
                          <span>{categoryLabel(item.category)}</span>
                          {item.mainItem?.sourceName && <span>{item.mainItem.sourceName}</span>}
                          <span>精选分 {Math.round(Number(item.score ?? 0))}</span>
                        </div>
                        <p>{item.summary || "待 AI 处理后生成中文摘要。"}</p>
                        {item.entryReason && <em>{item.entryReason}</em>}
                      </motion.article>
                    ))}
                  </motion.section>
                ))}
              </motion.article>
            )}
            {!loading && !daily && !error && (
              <section className="daily-document dark daily-empty">
                <p className="daily-volume">AIHOT DAILY</p>
                <h2>暂无日报</h2>
                <p className="daily-cover-summary">当前日期没有已发布日报，请从左侧归档选择其他日期，或稍后刷新。</p>
                <button className="ghost dark" onClick={reload}>刷新日报</button>
              </section>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
