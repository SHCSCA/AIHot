import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { KeyboardEvent } from "react";
import type { AgentDefinition } from "../../types/agents";
import { agents, AGENT_CATEGORIES, getAgentsByCategory, searchAgents } from "../../data/agents";
import { AgentCard } from "./AgentCard";

interface AgentPanelProps {
  open: boolean;
  onClose: () => void;
  onActivate?: (agent: AgentDefinition) => void;
}

export function AgentPanel({ open, onClose, onActivate }: AgentPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const filteredAgents = query.trim()
    ? searchAgents(query)
    : activeCategory
      ? getAgentsByCategory(activeCategory)
      : agents;

  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveCategory(null);
      setSelectedIndex(0);
      inputRef.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query, activeCategory]);

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filteredAgents.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const agent = filteredAgents[selectedIndex];
      if (agent) onActivate?.(agent);
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  }

  function selectCategory(cat: string | null) {
    setActiveCategory(cat);
    setQuery("");
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="cmdk-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="智能体专家面板"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          onClick={onClose}
        >
          <motion.div
            className="agent-panel"
            initial={{ x: "100%", opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "100%", opacity: 0 }}
            transition={{ duration: 0.28, ease: [0.4, 0, 0.2, 1] }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="agent-panel-header">
              <div className="agent-panel-title">
                <h2>智能体专家</h2>
                <p>选择垂直领域专家，获取深度情报分析</p>
              </div>
              <button className="agent-panel-close" onClick={onClose} aria-label="关闭">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            <div className="agent-search-wrap">
              <svg className="cmdk-search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <path d="m21 21-4.35-4.35" />
              </svg>
              <input
                ref={inputRef}
                className="cmdk-input"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="搜索智能体专家..."
                autoComplete="off"
              />
            </div>

            {!query && (
              <div className="agent-category-tabs">
                <button
                  className={`agent-category-tab ${activeCategory === null ? "active" : ""}`}
                  onClick={() => selectCategory(null)}
                >
                  全部
                </button>
                {AGENT_CATEGORIES.map((cat) => (
                  <button
                    key={cat.id}
                    className={`agent-category-tab ${activeCategory === cat.id ? "active" : ""}`}
                    onClick={() => selectCategory(cat.id)}
                  >
                    {cat.emoji} {cat.label}
                  </button>
                ))}
              </div>
            )}

            <div className="agent-list">
              {filteredAgents.length === 0 && (
                <p className="cmdk-empty">未找到匹配的智能体</p>
              )}
              {filteredAgents.map((agent, i) => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  compact={false}
                  onActivate={(a) => { onActivate?.(a); onClose(); }}
                />
              ))}
            </div>

            <div className="agent-panel-footer">
              <span>共 {filteredAgents.length} 个智能体</span>
              <span><kbd>ESC</kbd> 关闭</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function useAgentPanelShortcut(onToggle: () => void) {
  useEffect(() => {
    function handleKeyDown(e: globalThis.KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "a") {
        e.preventDefault();
        onToggle();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onToggle]);
}
