import { motion } from "framer-motion";
import { ArrowRight, Heart, RadioTower, Sparkles, TrendingUp, Zap } from "lucide-react";

type PublicChannel = "ai" | "amazon";

type BriefConfig = {
  eyebrow: string;
  title: string;
  summary: string;
  windowLabel: string;
  sourceState: string;
  primarySignal: string;
  secondarySignal: string;
  focus: string[];
  actions: string[];
  lead: {
    label: string;
    title: string;
    detail: string;
  };
};

const briefConfig: Record<PublicChannel, BriefConfig> = {
  ai: {
    eyebrow: "Reader Mode · AI Brief",
    title: "今日 AI 情报 Brief",
    summary: "把模型、产品、Agent、论文和行业变化收束成可读的事件线，优先呈现值得跟进的高信号变化。",
    windowLabel: "最近 24 小时",
    sourceState: "AI 信源池",
    primarySignal: "模型 / 产品 / Agent",
    secondarySignal: "论文 / 行业 / 商业化",
    focus: ["模型发布与能力变化", "Agent 工具链与开发者工作流", "论文、评测与产业化信号"],
    actions: ["阅读精选事件", "查看全部动态", "订阅日报"],
    lead: {
      label: "当前频道",
      title: "AI 热点",
      detail: "重点跟踪模型、产品、Agent、论文和行业变化。"
    }
  },
  amazon: {
    eyebrow: "Reader Mode · Seller Brief",
    title: "今日 Amazon 卖家 Brief",
    summary: "从政策、账号、FBA、广告、Listing、费用和选品变化中筛出卖家需要判断和行动的运营信号。",
    windowLabel: "最近 7 天",
    sourceState: "卖家信源池",
    primarySignal: "政策 / 账号 / 合规",
    secondarySignal: "FBA / 广告 / 费用",
    focus: ["政策与账号健康变动", "FBA、物流和费用调整", "广告、Listing 与选品机会"],
    actions: ["查看行动等级", "核对风险标签", "订阅卖家日报"],
    lead: {
      label: "当前频道",
      title: "Amazon 情报",
      detail: "重点跟踪平台政策、卖家运营和成本风险。"
    }
  }
};

const panelMotion = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0 }
};

export function HeroSection({ channel, sourceCount }: { channel: PublicChannel; sourceCount?: number }) {
  const brief = briefConfig[channel];
  const Icon = channel === "ai" ? Sparkles : Heart;
  const resolvedSourceCount = sourceCount == null ? "同步中" : sourceCount.toLocaleString();

  return (
    <section className="hero-section liquid-brief liquid-motion-enter" aria-label="AIHOT 情报总览">
      <div className="ambient-breathing-field" data-testid="ambient-breathing-field" aria-hidden="true">
        <span />
        <span />
        <span />
        <i />
      </div>

      <motion.div className="brief-primary liquid-glass-floating" variants={panelMotion} initial="hidden" animate="visible" transition={{ duration: 0.28 }}>
        <p className="brief-eyebrow">{brief.eyebrow}</p>
        <div className="brief-heading-row">
          <div>
            <h2>{brief.title}</h2>
            <p>{brief.summary}</p>
          </div>
          <span className="brief-channel-mark" aria-hidden="true">
            <Icon size={26} />
          </span>
        </div>

        <div className="brief-signal-grid" aria-label="当前情报状态">
          <div>
            <span>窗口范围</span>
            <strong>{brief.windowLabel}</strong>
          </div>
          <div>
            <span>{brief.sourceState}</span>
            <strong>{resolvedSourceCount}</strong>
          </div>
          <div>
            <span>主信号</span>
            <strong>{brief.primarySignal}</strong>
          </div>
        </div>

        <div className="brief-actions" aria-label="建议阅读动作">
          {brief.actions.map((action) => (
            <span key={action}><ArrowRight size={14} />{action}</span>
          ))}
        </div>
      </motion.div>

      <motion.div className="brief-side-stack" variants={panelMotion} initial="hidden" animate="visible" transition={{ duration: 0.28, delay: 0.08 }}>
        <article className="brief-side-card liquid-glass-panel">
          <span><RadioTower size={16} />{brief.lead.label}</span>
          <h3>{brief.lead.title}</h3>
          <p>{brief.lead.detail}</p>
        </article>
        <article className="brief-side-card liquid-glass-subtle">
          <span><TrendingUp size={16} />本轮关注</span>
          <ul>
            {brief.focus.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </article>
        <article className="brief-side-card liquid-glass-subtle">
          <span><Zap size={16} />辅助信号</span>
          <strong>{brief.secondarySignal}</strong>
          <p>切换到精选或全部情报流后，可继续用分类、日期、信源组和搜索收窄范围。</p>
        </article>
      </motion.div>
    </section>
  );
}
