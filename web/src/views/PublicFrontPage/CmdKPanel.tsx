import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Search } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

interface SearchResult {
  id: string;
  label: string;
  description?: string;
  category?: string;
}

const quickJumps: SearchResult[] = [
  { id: "pub:overview", label: "总览", description: "按当前频道查看情报总览", category: "快速跳转" },
  { id: "pub:selected", label: "精选", description: "当前频道自动挑选的高价值情报", category: "快速跳转" },
  { id: "pub:all", label: "全部热点", description: "全部情报流", category: "快速跳转" },
  { id: "pub:daily", label: "AI 日报", description: "杂志式每日摘要", category: "快速跳转" },
  { id: "pub:sources", label: "信源目录", description: "公开信源与采集档案", category: "快速跳转" },
  { id: "pub:feedback", label: "反馈", description: "提交内容质量反馈", category: "快速跳转" },
  { id: "admin:dashboard", label: "工作台", description: "运营总览", category: "快速跳转" },
  { id: "admin:sources", label: "信源管理", description: "维护信源", category: "快速跳转" },
  { id: "admin:events", label: "事件审核", description: "审核事件簇", category: "快速跳转" },
];

const HISTORY_KEY = "aihot_cmdk_history_v2";

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
  const panelRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const reducedMotion = useReducedMotion();
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  const allResults = query.trim()
    ? quickJumps.filter((r) =>
          r.label.toLowerCase().includes(query.toLowerCase()) ||
          r.description?.toLowerCase().includes(query.toLowerCase())
        )
    : [
        { id: "section:reader", label: "Reader Mode", description: "", category: "section" },
        ...quickJumps.filter((item) => item.id.startsWith("pub:")),
        { id: "section:ops", label: "Ops Mode", description: "", category: "section" },
        ...quickJumps.filter((item) => item.id.startsWith("admin:")),
      ];

  const historyItems = loadHistory().filter((h) =>
    h.toLowerCase().includes(query.toLowerCase())
  );

  const flatResults = allResults.filter((r) => r.category !== "section");

  useEffect(() => {
    if (open) {
      previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      setQuery("");
      setSelectedIndex(0);
      inputRef.current?.focus();
    }
    return () => {
      if (open) previousFocusRef.current?.focus();
    };
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

  function containPanelFocus(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key !== "Tab" || !panelRef.current) return;
    const focusable = [...panelRef.current.querySelectorAll<HTMLElement>(
      "input:not([disabled]), button:not([disabled]), a[href], [tabindex]:not([tabindex='-1'])"
    )];
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  function selectItem(item: SearchResult) {
    onSelect?.(item.id, item.label);
    const existing = loadHistory();
    saveHistory([item.label, ...existing.filter((historyItem) => historyItem !== item.label)]);
    if (item.id.startsWith("pub:")) {
      const section = item.id.replace("pub:", "");
      window.history.replaceState(null, "", section === "overview" ? "/" : `/${section}`);
    } else if (item.id.startsWith("admin:")) {
      const view = item.id.replace("admin:", "");
      window.history.replaceState(null, "", `/admin/${view}`);
    }
    onClose();
  }

  function renderSection(title: string, items: SearchResult[]) {
    return (
      <div key={title} className="cmdk-section">
        <p className="cmdk-section-title">{title}</p>
        {items.map((item) => {
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

  if (query.trim()) {
    if (flatResults.length > 0) sections.push({ title: "搜索结果", items: flatResults, startIdx: 0 });
  } else {
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
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="cmdk-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="命令面板"
          initial={{ opacity: reducedMotion ? 1 : 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: reducedMotion ? 1 : 0 }}
          transition={{ duration: reducedMotion ? 0 : 0.16 }}
          onClick={onClose}
        >
          <motion.div
            ref={panelRef}
            className="cmdk-panel qi-command-panel"
            initial={reducedMotion ? false : { y: -8, scale: 0.985, opacity: 0 }}
            animate={{ y: 0, scale: 1, opacity: 1 }}
            exit={reducedMotion ? { opacity: 0 } : { y: -5, scale: 0.99, opacity: 0 }}
            transition={{ duration: reducedMotion ? 0 : 0.2, ease: [0.22, 1, 0.36, 1] }}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={containPanelFocus}
          >
            <div className="cmdk-input-wrap">
              <Search className="cmdk-search-icon" size={18} aria-hidden="true" />
              <input
                ref={inputRef}
                className="cmdk-input"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                aria-label="搜索命令或页面"
                placeholder="搜索或快速跳转..."
                autoComplete="off"
              />
              <kbd className="cmdk-esc-hint">ESC</kbd>
            </div>

            <div className="cmdk-body">
              {sections.map((section) =>
                renderSection(section.title, section.items.filter((r) => r.category !== "section") as SearchResult[])
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
