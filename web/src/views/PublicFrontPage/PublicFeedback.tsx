import { useState } from "react";
import type { PublicApi } from "../../api";

type PublicChannel = "ai" | "amazon";

export function PublicFeedback({ api, channel }: { api: PublicApi; channel: PublicChannel }) {
  const [reason, setReason] = useState("");
  const [contact, setContact] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const trimmedReason = reason.trim();
  const canSubmit = trimmedReason.length >= 2 && !submitting;

  async function submit() {
    if (!canSubmit) {
      setMessage("请补充至少 2 个字的具体反馈内容。");
      return;
    }
    setSubmitting(true);
    try {
      await api.submitFeedback({
        channel,
        feedbackType: "general",
        contact: contact.trim() || undefined,
        reason: trimmedReason
      });
      setReason("");
      setContact("");
      setMessage("反馈已提交，后台会把它作为质量评估样本。");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "反馈提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="public-feedback liquid-glass-panel">
      <div>
        <p className="eyebrow">反馈闭环</p>
        <h2>提交质量信号</h2>
        <p>误选、漏选、日报结构、信源质量和页面体验都可以反馈。内容会进入后台评估，不会直接改动线上评分。</p>
      </div>
      <div className="feedback-form">
        <label className="feedback-reason">反馈内容
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="例如：某类内容不够准、日报结构想调整、页面哪里不顺手。"
            maxLength={2000}
            aria-describedby="feedback-minimum"
          />
        </label>
        <p id="feedback-minimum" className="hint">至少 2 个字，最多 2000 字。</p>
        <label>联系方式（选填）
          <input value={contact} onChange={(event) => setContact(event.target.value)} placeholder="邮箱 / 微信 / 手机号" />
        </label>
        {message && <p className={message.includes("已提交") ? "success" : "error"} role="status">{message}</p>}
        <button className="primary" onClick={submit} disabled={!canSubmit}>
          {submitting ? "提交中..." : "发送反馈"}
        </button>
      </div>
    </section>
  );
}
