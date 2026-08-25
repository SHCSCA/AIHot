import { BrainCircuit, Check, RefreshCw, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { useEffect, useState } from "react";
import type { AdminApi } from "../api";
import { Section } from "../components/Section";
import { useAsyncData } from "../hooks";
import type { SystemSettings } from "../types";
import { formatDateTime } from "../utils";

export function SystemSettingsView({ api }: { api: AdminApi }) {
  const { data, error, loading, reload } = useAsyncData<SystemSettings | null>(
    () => api.getSystemSettings(),
    null,
    []
  );
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (data) setEnabled(data.aiAnalysisEnabled);
  }, [data]);

  async function toggleAnalysis() {
    if (enabled === null) return;
    const next = !enabled;
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await api.updateSystemSettings({ aiAnalysisEnabled: next });
      setEnabled(updated.aiAnalysisEnabled);
      reload();
    } catch (cause) {
      setSaveError(cause instanceof Error ? cause.message : "保存失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  }

  const active = enabled ?? data?.aiAnalysisEnabled ?? false;

  return (
    <div className="view-stack system-settings-view">
      <Section
        title="系统设置"
        description="控制情报流水线是否调用外部 AI 分析服务。关闭后自动切换到内置基础规则。"
        error={error ?? saveError}
        action={
          <button className="ghost" onClick={reload} disabled={loading || saving}>
            <RefreshCw size={15} />
            {loading ? "同步中..." : "刷新状态"}
          </button>
        }
      >
        <div className="system-setting-panel">
          <div className="system-setting-lead">
            <div className={`system-setting-icon ${active ? "is-active" : "is-rules"}`} aria-hidden="true">
              {active ? <BrainCircuit size={25} /> : <SlidersHorizontal size={25} />}
            </div>
            <div>
              <p className="eyebrow">分析引擎</p>
              <h3>{active ? "AI 分析已启用" : "基础规则模式"}</h3>
              <p>
                {active
                  ? "流水线会使用当前配置的 AI provider 完成初筛、评分和事件证据分析。"
                  : "流水线不会发起任何 AI provider 请求，改用频道信号、信源权威度和确定性交叉验证。"}
              </p>
            </div>
          </div>
          <button
            className={`system-setting-switch ${active ? "is-on" : "is-off"}`}
            type="button"
            role="switch"
            aria-checked={active}
            aria-label={active ? "关闭 AI 分析" : "启用 AI 分析"}
            onClick={toggleAnalysis}
            disabled={enabled === null || saving}
          >
            <span className="system-setting-switch-track" aria-hidden="true">
              <span className="system-setting-switch-thumb"><Check size={13} /></span>
            </span>
            <span>{saving ? "保存中..." : active ? "已启用" : "已关闭"}</span>
          </button>
        </div>
      </Section>

      <Section title="当前运行策略" description="用于确认流水线实际采用的分析模式，不展示任何密钥信息。">
        <dl className="system-setting-facts">
          <div><dt>分析模式</dt><dd>{active ? "AI provider" : "内置基础规则"}</dd></div>
          <div><dt>Provider</dt><dd>{active ? data?.provider ?? "读取中" : "rules"}</dd></div>
          <div><dt>模型 / 规则版本</dt><dd>{active ? data?.model ?? "读取中" : "rules-v1"}</dd></div>
          <div><dt>最近修改</dt><dd>{data?.updatedBy ? `${data.updatedBy} · ${formatDateTime(data.updatedAt)}` : "尚未修改"}</dd></div>
        </dl>
        <p className="system-setting-note"><ShieldCheck size={15} />规则模式仍保留排序、精选阈值和多信源确定性交叉验证。</p>
      </Section>
    </div>
  );
}
