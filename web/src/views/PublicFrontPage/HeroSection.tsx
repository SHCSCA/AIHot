import { motion } from "framer-motion";
import { Heart, Sparkles, TrendingUp, Zap } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

interface BentoCardProps {
  children: ReactNode;
  className?: string;
  span?: string;
}

function BentoCard({ children, className = "", span = "" }: BentoCardProps) {
  return (
    <motion.div
      className={`bento-card breathing-bento ${span} ${className}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}

function AnimatedCounter({ target, duration = 1800 }: { target: number; duration?: number }) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    const start = performance.now();
    function tick(now: number) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.floor(eased * target));
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }, [target, duration]);

  return <span>{value.toLocaleString()}</span>;
}

function SmoothLineChart({ data, color = "#06b6d4" }: { data: number[]; color?: string }) {
  const width = 320;
  const height = 80;
  const padding = 8;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;

  const points = data.map((v, i) => {
    const x = padding + (i / (data.length - 1)) * (width - padding * 2);
    const y = padding + (1 - (v - min) / range) * (height - padding * 2);
    return `${x},${y}`;
  });

  const pathD = `M ${points.join(" L ")}`;
  const areaD = `${pathD} L ${width - padding},${height - padding} L ${padding},${height - padding} Z`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="bento-chart-svg" preserveAspectRatio="none">
      <defs>
        <linearGradient id={`grad-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <path d={areaD} fill={`url(#grad-${color.replace("#", "")})`} />
      <path d={pathD} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function HeroSection({ channel }: { channel: "ai" | "amazon" }) {
  const trendData = channel === "amazon" ? [8, 11, 9, 14, 10, 16, 13, 18, 15, 21, 17, 24] : [42, 68, 55, 79, 63, 88, 72, 95, 81, 103, 89, 118];
  const headline = channel === "amazon" ? "Amazon 卖家情报聚合" : "AI 与 Amazon 情报聚合";
  const description = channel === "amazon"
    ? "聚合平台政策、FBA、广告、Listing、费用和选品变化，保留卖家真正需要跟进的信号。"
    : "实时追踪 AI 模型、产品、Agent 工具与亚马逊卖家运营动态，基于信源质量、内容相关性和时效性多维评分精选。";
  const mainCount = channel === "amazon" ? 24 : 128;
  const sourceCount = channel === "amazon" ? 44 : 147;
  const eventCount = channel === "amazon" ? 7 : 23;
  return (
    <section className="hero-section breathing-hero" aria-label="AIHOT 情报总览">
      <div className="ambient-breathing-field" data-testid="ambient-breathing-field" aria-hidden="true">
        <span />
        <span />
        <span />
        <i />
      </div>
      <div className="bento-grid">
        {/* Main 2x2 card - 今日热点 */}
        <BentoCard span="bento-main" className="bento-card-main breathing-idle">
          <div className="bento-main-bg" aria-hidden="true">
            <svg className="bento-wave breathing-wave" viewBox="0 0 500 220" preserveAspectRatio="none">
              <path d="M0,110 C80,40 120,180 200,110 C280,40 320,180 400,110 C440,70 460,150 500,110 L500,220 L0,220 Z" fill="rgba(6,182,212,0.12)" />
              <path d="M0,140 C60,80 140,200 220,140 C300,80 360,200 440,140 C470,110 490,160 500,140 L500,220 L0,220 Z" fill="rgba(6,182,212,0.08)" />
              <path d="M0,170 C100,120 200,220 300,170 C400,120 450,200 500,170 L500,220 L0,220 Z" fill="rgba(6,182,212,0.05)" />
            </svg>
          </div>
          <div className="bento-main-content">
            <span className="bento-badge">
              <Sparkles size={13} />
              今日热点
            </span>
            <h2 className="bento-main-title">{headline}</h2>
            <p className="bento-main-desc">
              {description}
            </p>
            <div className="bento-main-stats">
              <div className="bento-stat">
                <span className="bento-stat-value">
                  <AnimatedCounter target={mainCount} />
                </span>
                <span className="bento-stat-label">今日情报</span>
              </div>
              <div className="bento-stat">
                <span className="bento-stat-value">
                  <AnimatedCounter target={sourceCount} />
                </span>
                <span className="bento-stat-label">来源数</span>
              </div>
              <div className="bento-stat">
                <span className="bento-stat-value">
                  <AnimatedCounter target={eventCount} />
                </span>
                <span className="bento-stat-label">{channel === "amazon" ? "卖家事件" : "AI 事件"}</span>
              </div>
            </div>
          </div>
        </BentoCard>

        {/* Trend chart card */}
        <BentoCard className="bento-card-chart">
          <div className="bento-card-header">
            <TrendingUp size={16} className="text-cyan" />
            <span>情报热度趋势</span>
          </div>
          <SmoothLineChart data={trendData} color="#06b6d4" />
          <p className="bento-chart-label">近 12 小时精选情报量</p>
        </BentoCard>

        {/* AI channel card */}
        <BentoCard className="bento-card-channel">
          <div className="bento-card-header">
            <Sparkles size={16} className="text-violet" />
            <span>AI 热点</span>
          </div>
          <div className="bento-channel-stats">
            <div className="bento-big-num">
              <AnimatedCounter target={847} />
            </div>
            <p>AI 相关事件</p>
          </div>
          <div className="bento-channel-tags">
            <span className="bento-tag">模型发布</span>
            <span className="bento-tag">产品更新</span>
            <span className="bento-tag">Agent</span>
          </div>
        </BentoCard>

        {/* Amazon channel card */}
        <BentoCard className="bento-card-channel">
          <div className="bento-card-header">
            <Heart size={16} className="text-rose" />
            <span>Amazon 情报</span>
          </div>
          <div className="bento-channel-stats">
            <div className="bento-big-num">
              <AnimatedCounter target={623} />
            </div>
            <p>卖家相关内容</p>
          </div>
          <div className="bento-channel-tags">
            <span className="bento-tag">FBA</span>
            <span className="bento-tag">广告</span>
            <span className="bento-tag">政策</span>
          </div>
        </BentoCard>

        {/* Quick stats card */}
        <BentoCard className="bento-card-quick">
          <div className="bento-card-header">
            <Zap size={16} className="text-amber" />
            <span>快速统计</span>
          </div>
          <div className="bento-quick-list">
            <div className="bento-quick-item">
              <span>信源总数</span>
              <strong>2,841</strong>
            </div>
            <div className="bento-quick-item">
              <span>今日日报</span>
              <strong>已发布</strong>
            </div>
            <div className="bento-quick-item">
              <span>平均置信度</span>
              <strong>87%</strong>
            </div>
          </div>
        </BentoCard>
      </div>

      <style>{`
        .hero-section {
          padding: 24px 0 32px;
        }

        .bento-grid {
          display: grid;
          grid-template-columns: repeat(12, 1fr);
          gap: 16px;
        }

        .bento-card {
          padding: 22px;
          border-radius: 22px;
          background: linear-gradient(135deg, rgba(31,41,59,0.78), rgba(19,27,43,0.86));
          border: 1px solid rgba(148,163,184,0.16);
          box-shadow: 0 24px 70px rgba(0,0,0,0.22);
          backdrop-filter: blur(18px);
          cursor: default;
        }

        .bento-main {
          grid-column: span 8;
          grid-row: span 2;
          position: relative;
          overflow: hidden;
        }

        .bento-card-chart {
          grid-column: span 4;
        }

        .bento-card-channel {
          grid-column: span 4;
        }

        .bento-card-quick {
          grid-column: span 4;
        }

        .bento-main-bg {
          position: absolute;
          inset: 0;
          pointer-events: none;
        }

        .bento-wave {
          width: 100%;
          height: 100%;
        }

        .bento-main-content {
          position: relative;
          z-index: 1;
          display: flex;
          flex-direction: column;
          height: 100%;
        }

        .bento-badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 5px 12px;
          border-radius: 999px;
          background: rgba(6,182,212,0.18);
          border: 1px solid rgba(6,182,212,0.35);
          color: #67e8f9;
          font-size: 12px;
          font-weight: 600;
          width: fit-content;
          margin-bottom: 14px;
        }

        .bento-main-title {
          margin: 0 0 10px;
          color: #f8fafc;
          font-size: 26px;
          font-weight: 700;
          line-height: 1.3;
        }

        .bento-main-desc {
          margin: 0;
          color: #94a3b8;
          font-size: 14px;
          line-height: 1.65;
          flex: 1;
        }

        .bento-main-stats {
          display: flex;
          gap: 28px;
          margin-top: 20px;
          padding-top: 18px;
          border-top: 1px solid rgba(148,163,184,0.12);
        }

        .bento-stat {
          display: flex;
          flex-direction: column;
          gap: 3px;
        }

        .bento-stat-value {
          font-size: 28px;
          font-weight: 700;
          color: #67e8f9;
          line-height: 1;
        }

        .bento-stat-label {
          font-size: 12px;
          color: #64748b;
        }

        .bento-card-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 14px;
          color: #94a3b8;
          font-size: 13px;
          font-weight: 500;
        }

        .text-cyan { color: #06b6d4; }
        .text-violet { color: #8b5cf6; }
        .text-rose { color: #f43f5e; }
        .text-amber { color: #f59e0b; }

        .bento-chart-svg {
          width: 100%;
          height: 80px;
        }

        .bento-chart-label {
          margin: 8px 0 0;
          font-size: 11px;
          color: #475569;
          text-align: center;
        }

        .bento-channel-stats {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          flex: 1;
          padding: 8px 0;
        }

        .bento-big-num {
          font-size: 48px;
          font-weight: 700;
          color: #f8fafc;
          line-height: 1;
        }

        .bento-channel-stats p {
          margin: 6px 0 0;
          font-size: 12px;
          color: #64748b;
        }

        .bento-channel-tags {
          display: flex;
          gap: 6px;
          flex-wrap: wrap;
          margin-top: 12px;
        }

        .bento-tag {
          padding: 3px 10px;
          border-radius: 999px;
          background: rgba(148,163,184,0.1);
          border: 1px solid rgba(148,163,184,0.15);
          color: #94a3b8;
          font-size: 11px;
        }

        .bento-quick-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .bento-quick-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 13px;
          color: #64748b;
        }

        .bento-quick-item strong {
          color: #e2e8f0;
          font-weight: 600;
        }

        @media (max-width: 1024px) {
          .bento-main { grid-column: span 12; }
          .bento-card-chart { grid-column: span 6; }
          .bento-card-channel { grid-column: span 6; }
          .bento-card-quick { grid-column: span 6; }
        }

        @media (max-width: 640px) {
          .bento-grid { grid-template-columns: 1fr; }
          .bento-main,
          .bento-card-chart,
          .bento-card-channel,
          .bento-card-quick { grid-column: span 1; }
        }
      `}</style>
    </section>
  );
}
