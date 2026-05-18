import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

interface SearchResult {
  id: string;
  label: string;
  description?: string;
  category?: string;
}

const quickJumps: SearchResult[] = [
  { id: "pub:selected", label: "精选", description: "AI 自动挑选的高价值情报", category: "快速跳转" },
  { id: "pub:all", label: "全部热点", description: "全部情报流", category: "快速跳转" },
  { id: "pub:daily", label: "AI 日报", description: "杂志式每日摘要", category: "快速跳转" },
  { id: "pub:sources", label: "信源墙", description: "公开信源列表", category: "快速跳转" },
  { id: "pub:feedback", label: "反馈", description: "提交内容质量反馈", category: "快速跳转" },
  { id: "admin:dashboard", label: "工作台", description: "运营总览", category: "快速跳转" },
  { id: "admin:sources", label: "信源管理", description: "维护信源", category: "快速跳转" },
  { id: "admin:events", label: "事件审核", description: "审核事件簇", category: "快速跳转" },
];

const hotIntelligence: SearchResult[] = [
  { id: "hot:1", label: "Claude 4 发布", description: "Anthropic 推出新一代多模态模型", category: "热门情报" },
  { id: "hot:2", label: "Amazon FBA 新规", description: "物流费用即将调整", category: "热门情报" },
  { id: "hot:3", label: "GPT-5  rumored", description: "OpenAI 下一代模型传闻", category: "热门情报" },
  { id: "hot:4", label: "TikTok Shop 新政", description: "电商渠道政策变动", category: "热门情报" },
];

const HISTORY_KEY = "aihot_cmdk_history";

function loadHistory(): string[] {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function saveHistory(history: string[]) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 8)));
}

interface CmdKPanelProps {
  open: boolean;
  onClose: () => void;
  onSelect?: (id: string, label: string) => void;
}

export function CmdKPanel({ open, onClose, onSelect }: CmdKPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  const allResults = query.trim()
    ? [
        ...hotIntelligence.filter((r) =>
          r.label.toLowerCase().includes(query.toLowerCase()) ||
          r.description?.toLowerCase().includes(query.toLowerCase())
        ),
        ...quickJumps.filter((r) =>
          r.label.toLowerCase().includes(query.toLowerCase()) ||
          r.description?.toLowerCase().includes(query.toLowerCase())
        ),
      ]
    : [
        { id: "section:quick", label: "快速跳转", description: "", category: "section" },
        ...quickJumps.slice(0, 3),
        { id: "section:daily", label: "热门情报", description: "", category: "section" },
        ...hotIntelligence,
      ];

  const historyItems = loadHistory().filter((h) =>
    h.toLowerCase().includes(query.toLowerCase())
  );

  const flatResults = allResults.filter((r) => r.category !== "section");

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      inputRef.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, flatResults.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = flatResults[selectedIndex];
      if (item) selectItem(item);
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  }

  function selectItem(item: SearchResult) {
    onSelect?.(item.id, item.label);
    if (item.id.startsWith("pub:")) {
      const section = item.id.replace("pub:", "");
      window.history.replaceState(null, "", section === "selected" ? "/" : `/${section}`);
    } else if (item.id.startsWith("admin:")) {
      const view = item.id.replace("admin:", "");
      window.history.replaceState(null, "", `/admin/${view}`);
    } else {
      const existing = loadHistory();
      saveHistory([item.label, ...existing.filter((h) => h !== item.label)]);
    }
    onClose();
  }

  function renderSection(title: string, items: SearchResult[], startIdx: number) {
    return (
      <div key={title} className="cmdk-section">
        <p className="cmdk-section-title">{title}</p>
        {items.map((item, i) => {
          const globalIdx = flatResults.indexOf(item);
          const isSelected = globalIdx === selectedIndex;
          return (
            <button
              key={item.id}
              className={`cmdk-result ${isSelected ? "selected" : ""}`}
              onClick={() => selectItem(item)}
              onMouseEnter={() => setSelectedIndex(globalIdx)}
            >
              <span className="cmdk-result-label">{item.label}</span>
              {item.description && (
                <span className="cmdk-result-desc">{item.description}</span>
              )}
            </button>
          );
        })}
      </div>
    );
  }

  let currentSection = "";
  let sectionStartIdx = 0;
  const sections: { title: string; items: SearchResult[]; startIdx: number }[] = [];

  allResults.forEach((item, i) => {
    if (item.category === "section") {
      if (currentSection) {
        sections.push({
          title: currentSection,
          items: allResults.slice(sectionStartIdx, i) as SearchResult[],
          startIdx: sectionStartIdx,
        });
      }
      currentSection = item.label;
      sectionStartIdx = i + 1;
    }
  });
  if (currentSection) {
    sections.push({
      title: currentSection,
      items: allResults.slice(sectionStartIdx) as SearchResult[],
      startIdx: sectionStartIdx,
    });
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="cmdk-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="命令面板"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          onClick={onClose}
        >
          <motion.div
            className="cmdk-panel"
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ duration: 0.18, ease: [0.4, 0, 0.2, 1] }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="cmdk-input-wrap">
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
                placeholder="搜索或快速跳转..."
                autoComplete="off"
              />
              <kbd className="cmdk-esc-hint">ESC</kbd>
            </div>

            <div className="cmdk-body">
              {sections.map((section) =>
                renderSection(section.title, section.items.filter((r) => r.category !== "section") as SearchResult[], section.startIdx)
              )}
              {historyItems.length > 0 && !query && (
                <div className="cmdk-section">
                  <p className="cmdk-section-title">历史搜索</p>
                  {historyItems.slice(0, 4).map((h) => (
                    <button key={h} className="cmdk-result" onClick={() => { setQuery(h); inputRef.current?.focus(); }}>
                      <span className="cmdk-result-label">{h}</span>
                    </button>
                  ))}
                </div>
              )}
              {flatResults.length === 0 && query && (
                <p className="cmdk-empty">未找到相关结果</p>
              )}
            </div>

            <div className="cmdk-footer">
              <span><kbd>↑↓</kbd> 导航</span>
              <span><kbd>↵</kbd> 选中</span>
              <span><kbd>ESC</kbd> 关闭</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function useCmdKShortcut(onToggle: () => void) {
  useEffect(() => {
    function handleKeyDown(e: globalThis.KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onToggle();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onToggle]);
}
