import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight, ExternalLink, FileSearch, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { EventMember, MainItem, PublicEvent, PublicEventDetail } from "../../types";
import { useAsyncData } from "../../hooks";
import { formatDateTime, formatMonthDay, formatTime } from "../../utils";
import { categoryLabel, sourceGroupLabel, sellerActionLevelLabel } from "../../labels";

interface EventCardExpandProps {
  event: PublicEvent;
  api: { getEventDetail: (id: string) => Promise<PublicEventDetail | null> };
  showDate: boolean;
  index: number;
}

export function EventCardExpand({ event, api, showDate, index }: EventCardExpandProps) {
  const [open, setOpen] = useState(false);
  const reducedMotion = useReducedMotion();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const { data: detail, loading, error } = useAsyncData<PublicEventDetail | null>(
    () => (open ? api.getEventDetail(event.id) : Promise.resolve(null)),
    null,
    [open, event.id, api]
  );

  useEffect(() => {
    if (!open) return;
    const appRoot = document.getElementById("root");
    const scrollContainer = document.querySelector<HTMLElement>(".unified-main");
    const previousOverflow = document.body.style.overflow;
    const previousContainerOverflow = scrollContainer?.style.overflow ?? "";
    const previousRootInert = appRoot?.inert ?? false;
    const previousRootAriaHidden = appRoot?.getAttribute("aria-hidden") ?? null;
    document.body.style.overflow = "hidden";
    if (scrollContainer) scrollContainer.style.overflow = "hidden";
    closeRef.current?.focus();
    if (appRoot) {
      appRoot.inert = true;
      appRoot.setAttribute("aria-hidden", "true");
    }

    const containDialogFocus = (keyboardEvent: KeyboardEvent) => {
      if (keyboardEvent.key === "Escape") {
        keyboardEvent.preventDefault();
        setOpen(false);
        return;
      }
      if (keyboardEvent.key !== "Tab" || !dialogRef.current) return;

      const focusable = [...dialogRef.current.querySelectorAll<HTMLElement>(
        "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"
      )].filter((element) => !element.hasAttribute("hidden") && element.getAttribute("aria-hidden") !== "true");
      if (focusable.length === 0) {
        keyboardEvent.preventDefault();
        dialogRef.current.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (keyboardEvent.shiftKey && (active === first || !dialogRef.current.contains(active))) {
        keyboardEvent.preventDefault();
        last.focus();
      } else if (!keyboardEvent.shiftKey && active === last) {
        keyboardEvent.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", containDialogFocus);
    return () => {
      document.body.style.overflow = previousOverflow;
      if (scrollContainer) scrollContainer.style.overflow = previousContainerOverflow;
      if (appRoot) {
        appRoot.inert = previousRootInert;
        if (previousRootAriaHidden == null) appRoot.removeAttribute("aria-hidden");
        else appRoot.setAttribute("aria-hidden", previousRootAriaHidden);
      }
      window.removeEventListener("keydown", containDialogFocus);
      triggerRef.current?.focus();
    };
  }, [open]);

  const summary = event.summary || event.mainItem?.summary || "待 AI 处理后生成中文摘要。";
  const reason = formatReason(event.entryReason || `来自 ${event.sourceCount} 个来源，系统评分达到精选阈值。`);
  const suggestedAction = event.suggestedAction || (event.channel === "amazon" && event.sellerActionLevel
    ? sellerActionLevelLabel(event.sellerActionLevel)
    : "继续核对主来源与相关证据，再决定是否跟进。");
  const scoreClass = event.score > 85 ? "score-high" : event.score >= 70 ? "score-mid" : "score-low";
  const signalTags = event.channel === "amazon" ? amazonSignalTags(event) : aiSignalTags(event);
  const visibleTags = signalTags.slice(0, 3);
  const hiddenTagCount = Math.max(signalTags.length - visibleTags.length, 0);
  const detailId = `event-detail-${event.id}`;
  const detailEvent = detail?.event ?? event;
  const members = detail?.members ?? [];
  const mainMember = members.find((member) => member.isMain);
  const mainSource = mainMember ?? detailEvent.mainItem ?? event.mainItem;
  const relatedMembers = members.filter((member) => !member.isMain);
  const keyFacts = detailEvent.keyFacts?.filter(Boolean) ?? [];
  const supportedFacts = detailEvent.supportedFacts?.filter(Boolean) ?? [];
  const supportedClaims = detailEvent.supportedClaims?.filter((claim) => claim.claim) ?? [];
  const conflictingClaims = detailEvent.conflictingClaims?.filter(Boolean) ?? [];
  const verification = verificationMeta(detailEvent.verificationStatus);
  const evidenceStatus = loading
    ? "正在核对来源与证据链。"
    : error
      ? ""
      : open
        ? `证据加载完成，共 ${detailEvent.independentSourceCount ?? detailEvent.sourceCount ?? event.sourceCount} 个独立发布方。`
        : "";

  const detailPortal = typeof document === "undefined" ? null : createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="qi-evidence-layer"
          initial={{ opacity: reducedMotion ? 1 : 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: reducedMotion ? 1 : 0 }}
          transition={{ duration: reducedMotion ? 0 : 0.2 }}
        >
          <div className="qi-evidence-backdrop" aria-hidden="true" onClick={() => setOpen(false)} />
          <motion.aside
            ref={dialogRef}
            id={detailId}
            className="qi-evidence-drawer liquid-glass-floating"
            role="dialog"
            aria-modal="true"
            aria-labelledby={`${detailId}-title`}
            tabIndex={-1}
            initial={reducedMotion ? false : { x: "100%" }}
            animate={{ x: 0 }}
            exit={reducedMotion ? { opacity: 0 } : { x: "100%" }}
            transition={{ duration: reducedMotion ? 0 : 0.34, ease: [0.22, 1, 0.36, 1] }}
          >
            <header className="qi-evidence-header">
              <div>
                <span><FileSearch size={15} />事件证据</span>
                <h2 id={`${detailId}-title`}>{event.title}</h2>
              </div>
              <button ref={closeRef} className="icon-button" type="button" onClick={() => setOpen(false)} aria-label="关闭事件详情">
                <X size={19} />
              </button>
            </header>

            <div className="qi-evidence-body" aria-busy={loading}>
              <div className="qi-live-status" role="status" aria-live="polite" aria-atomic="true">{evidenceStatus}</div>
              {loading && <div className="qi-drawer-loading">正在核对来源与证据链...</div>}
              {error && <p className="error" role="alert">{error}</p>}
              {!loading && !error && (
                <>
                  <section className="event-detail-section event-detail-member-summary" aria-label="成员来源">
                    <div className="qi-evidence-section-title"><h3>证据概览</h3><span>{members.length || detailEvent.memberCount || event.memberCount} 条成员</span></div>
                    <div className="event-detail-stats">
                      <span><strong>{detailEvent.independentSourceCount ?? detailEvent.sourceCount ?? event.sourceCount}</strong> 个独立发布方</span>
                      <span><strong>{detailEvent.authoritativeSourceCount ?? event.authoritativeSourceCount ?? 0}</strong> 个权威信源</span>
                      <span><strong>{Math.round(detailEvent.evidenceScore ?? event.evidenceScore ?? 0)}</strong> 证据分</span>
                    </div>
                  </section>

                  <section className={`event-detail-section qi-verification-panel is-${verification.tone}`} aria-label="交叉验证结论">
                    <div className="qi-evidence-section-title">
                      <h3>交叉验证结论</h3>
                      <span className={`qi-verification-badge is-${verification.tone}`}>{verification.label}</span>
                    </div>
                    <p>{detailEvent.evidenceSummary || verification.description}</p>
                    {(supportedClaims.length > 0 || supportedFacts.length > 0) && (
                      <div className="qi-evidence-fact-group">
                        <strong>多源支持事实</strong>
                        {supportedClaims.length > 0 ? (
                          <ul>
                            {supportedClaims.map((supported) => {
                              const supporterNames = supported.sourceIds
                                .map((sourceId) => members.find((member) => member.sourceId === sourceId)?.sourceName)
                                .filter((name): name is string => Boolean(name));
                              return (
                                <li key={`${supported.claim}-${supported.publisherKeys.join("-")}`}>
                                  <span>{supported.claim}</span>
                                  <small className="qi-evidence-supporters">
                                    支持方：{supporterNames.length > 0 ? supporterNames.join("、") : supported.publisherKeys.join("、")}
                                  </small>
                                </li>
                              );
                            })}
                          </ul>
                        ) : (
                          <ul>{supportedFacts.map((fact) => <li key={fact}>{fact}</li>)}</ul>
                        )}
                      </div>
                    )}
                    {conflictingClaims.length > 0 && (
                      <div className="qi-evidence-fact-group is-conflict">
                        <strong>待核对冲突</strong>
                        <ul>{conflictingClaims.map((claim) => <li key={claim}>{claim}</li>)}</ul>
                      </div>
                    )}
                  </section>

                  <section className="event-detail-section" aria-label="主来源">
                    <div className="qi-evidence-section-title"><h3>主来源</h3><span>PRIMARY</span></div>
                    {mainSource ? <SourceEvidenceLink item={mainSource} relation="主来源" /> : <p className="hint">暂无主来源信息。</p>}
                  </section>

                  <section className="event-detail-section" aria-label="相关来源">
                    <div className="qi-evidence-section-title"><h3>相关来源</h3><span>{relatedMembers.length}</span></div>
                    {relatedMembers.length > 0 ? relatedMembers.map((member) => (
                      <SourceEvidenceLink key={member.id} item={member} relation={memberRelation(member)} />
                    )) : <p className="hint">暂无更多相关来源。</p>}
                  </section>

                  <section className="event-detail-section" aria-label="证据链">
                    <div className="qi-evidence-section-title"><h3>证据链</h3><span>TRACE</span></div>
                    <ol className="event-evidence-chain">
                      {keyFacts.map((fact) => <li key={fact}>{fact}</li>)}
                      {members.map((member) => (
                        <li key={`member-${member.id}`}>
                          {member.isMain ? "主来源" : "相关来源"}：{member.title}
                          {member.sourceName ? ` · ${member.sourceName}` : ""}
                        </li>
                      ))}
                    </ol>
                    {keyFacts.length === 0 && members.length === 0 && <p className="hint">详情暂无证据链条目。</p>}
                  </section>
                </>
              )}
            </div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );

  return (
    <>
      <motion.article
        className="aihot-event qi-event"
        initial={reducedMotion ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: reducedMotion ? 0 : 0.28, delay: reducedMotion ? 0 : Math.min(index, 4) * 0.025 }}
      >
        <div className="timeline-stamp dark">
          {showDate && <span className="timeline-date">{formatMonthDay(event.lastSeenAt)}</span>}
          <strong>{formatTime(event.lastSeenAt)}</strong>
          <i aria-hidden="true" />
        </div>

        <div className="aihot-event-card qi-event-card">
          <div className="event-meta dark">
            <span>{event.mainItem?.sourceName ?? "未知来源"}</span>
            <span>{categoryLabel(event.category)}</span>
            <span>{formatDateTime(event.lastSeenAt)}</span>
          </div>

          <div className="event-title-row">
            <h2>{event.title}</h2>
            <div className="qi-event-signals">
              <span className={`qi-verification-badge is-${verification.tone}`} aria-label={`交叉验证状态：${verification.label}`}>
                {verification.label}
              </span>
              <strong className={`score-badge ${scoreClass}`} aria-label={`精选分 ${Math.round(event.score)}`}>
                精选分 {Math.round(event.score)}
              </strong>
            </div>
          </div>

          {event.mainItem?.imageUrl && (
            <figure className="event-media event-media-natural">
              <img src={event.mainItem.imageUrl} alt={event.mainItem.imageAlt || event.title} loading="lazy" />
            </figure>
          )}

          <p className="event-summary">{summary}</p>

          {visibleTags.length > 0 && (
            <div className="event-tags dark" role="list" aria-label="事件标签">
              {visibleTags.map((tag) => <span className={tagClass(tag)} key={tag} role="listitem">{tag}</span>)}
              {hiddenTagCount > 0 && <span className="tag-more" role="listitem">+{hiddenTagCount}</span>}
            </div>
          )}

          <div className="event-decision-panel" aria-label="入选依据和建议动作">
            <div className="event-rationale">
              <small>入选依据</small>
              <p>{reason}</p>
            </div>
            <div className="event-next-step" aria-label="建议动作">
              <small>建议动作</small>
              <strong>{suggestedAction}</strong>
              <div>
                {event.sellerActionLevel && <em>{sellerActionLevelLabel(event.sellerActionLevel)}</em>}
                {event.confidenceScore != null && <em>置信度 {Math.round(event.confidenceScore)}</em>}
              </div>
            </div>
          </div>

          <div className="event-foot">
            <span className="qi-event-evidence-count"><strong>{event.sourceCount}</strong> 个来源 · <strong>{event.memberCount}</strong> 条相关</span>
            <div className="qi-event-actions">
              {event.mainItem?.url && (
                <a href={event.mainItem.url} target="_blank" rel="noreferrer">
                  查看原文<ExternalLink size={14} />
                </a>
              )}
              <button
                ref={triggerRef}
                className="ghost dark qi-detail-trigger"
                type="button"
                onClick={() => setOpen(true)}
                aria-expanded={open}
                aria-controls={detailId}
              >
                证据详情<ArrowUpRight size={15} />
              </button>
            </div>
          </div>
        </div>
      </motion.article>
      {detailPortal}
    </>
  );
}

function formatReason(reason: string) {
  return reason.replace(/^推荐理由[：:]\s*/, "");
}

function aiSignalTags(event: PublicEvent): string[] {
  const category = categoryLabel(event.category);
  const tags = event.tags ?? [];
  return unique([category, ...tags.filter((tag) => /模型|产品|Agent|工具|论文|报告|行业|商业|API|OpenAI|GPT|Claude|Gemini|开源|研究|评测/i.test(tag)), ...tags]).slice(0, 8);
}

function amazonSignalTags(event: PublicEvent): string[] {
  const action = event.sellerActionLevel ? sellerActionLevelLabel(event.sellerActionLevel) : null;
  const category = categoryLabel(event.category);
  const tags = event.tags ?? [];
  return unique([action, category, ...tags.filter((tag) => /风险|合规|账号|账户|FBA|费用|费率|利润|库存|物流|Listing|广告|政策|赔付|选品|税务/i.test(tag)), ...tags]).slice(0, 8);
}

function unique(values: Array<string | null | undefined>): string[] {
  return values.filter((value, index, list): value is string => Boolean(value) && list.indexOf(value) === index);
}

function tagClass(tag: string) {
  if (/风险|合规|账号|账户|费用|费率|利润|税务/.test(tag)) return "tag-risk";
  if (/行动|建议|广告|Listing|FBA|库存|物流|赔付|API/.test(tag)) return "tag-action";
  if (/OpenAI|GPT|Claude|Gemini|Amazon|SP-API/i.test(tag)) return "tag-keyword";
  return "tag-normal";
}

function verificationMeta(status: PublicEvent["verificationStatus"]) {
  if (status === "corroborated") {
    return { label: "已交叉验证", tone: "verified", description: "至少两个独立发布方支持同一组关键事实。" };
  }
  if (status === "conflicted") {
    return { label: "证据有冲突", tone: "conflict", description: "不同来源存在关键说法冲突，建议暂缓行动并继续核对。" };
  }
  if (status === "insufficient") {
    return { label: "证据待补强", tone: "pending", description: "已有多个来源，但共同事实或证据强度仍不足。" };
  }
  if (status === "single_source") {
    return { label: "单一信源", tone: "single", description: "当前只有一个独立发布方，不应视为已完成交叉验证。" };
  }
  return { label: "待验证", tone: "pending", description: "该事件尚未完成新一轮证据评估。" };
}

function SourceEvidenceLink({ item, relation }: { item: MainItem | EventMember; relation: string }) {
  const body = (
    <>
      <strong>{item.title}</strong>
      <span>{sourceMeta(item, relation)}</span>
    </>
  );

  if (!item.url) return <div className="event-source-link event-source-link-muted">{body}</div>;

  return (
    <a className="event-source-link" href={item.url} target="_blank" rel="noreferrer">
      <span>{body}</span><ArrowUpRight size={16} aria-hidden="true" />
    </a>
  );
}

function sourceMeta(item: MainItem | EventMember, relation: string): string {
  const meta = [item.sourceName ?? "未知来源", relation, sourceGroupLabel(item.sourceGroup), item.sourceTier]
    .filter(Boolean)
    .join(" · ");
  const publishedAt = item.publishedAt ? ` · ${formatDateTime(item.publishedAt)}` : "";
  return `${meta}${publishedAt}`;
}

function memberRelation(member: EventMember): string {
  const relation = member.isMain ? "主来源" : "相关来源";
  return typeof member.relationScore === "number" ? `${relation} · 关联 ${Math.round(member.relationScore)}` : relation;
}
