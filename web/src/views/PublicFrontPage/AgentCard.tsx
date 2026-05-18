import { motion } from "framer-motion";
import type { AgentDefinition } from "../../types/agents";

interface AgentCardProps {
  agent: AgentDefinition;
  compact?: boolean;
  onActivate?: (agent: AgentDefinition) => void;
}

export function AgentCard({ agent, compact = false, onActivate }: AgentCardProps) {
  return (
    <motion.article
      className={`agent-card ${compact ? "compact" : ""}`}
      style={{ "--agent-color": agent.color } as React.CSSProperties}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.02 }}
      transition={{ duration: 0.25 }}
      onClick={() => onActivate?.(agent)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onActivate?.(agent); }}
    >
      <div className="agent-card-header">
        <span className="agent-emoji">{agent.emoji}</span>
        <div className="agent-meta">
          <h3 className="agent-name">{agent.name}</h3>
          <span className="agent-domain">{agent.domain}</span>
        </div>
        <span className="agent-category-tag">{agent.category}</span>
      </div>

      {!compact && (
        <>
          <p className="agent-description">{agent.description}</p>
          <div className="agent-capabilities">
            {agent.capabilities.slice(0, 4).map((cap) => (
              <span key={cap} className="capability-tag">{cap}</span>
            ))}
            {agent.capabilities.length > 4 && (
              <span className="capability-more">+{agent.capabilities.length - 4}</span>
            )}
          </div>
        </>
      )}

      <div className="agent-card-footer">
        <span className="agent-id">@{agent.id}</span>
        <motion.button
          className="agent-activate-btn"
          style={{ background: agent.color }}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={(e) => { e.stopPropagation(); onActivate?.(agent); }}
        >
          激活
        </motion.button>
      </div>
    </motion.article>
  );
}