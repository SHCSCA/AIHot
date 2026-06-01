import { Heart, LockKeyhole, Moon, Monitor, Search, Sparkles, Sun } from "lucide-react";
import { motion } from "framer-motion";
import type { PublicChannel, PublicSection } from "./index";

type ThemePreference = "dark" | "light" | "system";

interface TopNavProps {
  channel: PublicChannel;
  section: PublicSection;
  theme: ThemePreference;
  filters: { q: string };
  onChannelChange: (channel: PublicChannel) => void;
  onSectionChange: (section: PublicSection) => void;
  onThemeChange: (theme: ThemePreference) => void;
  onSearchChange: (q: string) => void;
  onLoginClick: () => void;
  hideLoginControls?: boolean;
}

const channelItems = [
  { id: "ai" as const, label: "AI 热点", Icon: Sparkles },
  { id: "amazon" as const, label: "亚马逊情报", Icon: Heart }
];

const sectionItems = [
  { id: "overview" as const, label: "总览" },
  { id: "selected" as const, label: "精选" },
  { id: "all" as const, label: "全部热点" },
  { id: "daily" as const, label: "日报" },
  { id: "rss" as const, label: "RSS 订阅" },
  { id: "sources" as const, label: "信源墙" },
  { id: "feedback" as const, label: "反馈" }
];

export function TopNav({
  channel,
  section,
  theme,
  filters,
  onChannelChange,
  onSectionChange,
  onThemeChange,
  onSearchChange,
  onLoginClick,
  hideLoginControls
}: TopNavProps) {
  return (
    <header className="aihot-topnav liquid-glass-panel">
      <div className="topnav-logo">
        <span>AI</span><i />HOT
      </div>

      <nav className="unified-channel-switch" aria-label="频道分区">
        {channelItems.map(({ id, label, Icon }) => (
          <motion.button
            key={id}
            className={channel === id ? "active" : ""}
            onClick={() => onChannelChange(id)}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.98 }}
          >
            <Icon size={15} />
            <span>{label}</span>
          </motion.button>
        ))}
      </nav>

      <nav className="topnav-sections" aria-label="频道内功能">
        {sectionItems.map(({ id, label }) => (
          <motion.button
            key={id}
            className={section === id ? "active" : ""}
            onClick={() => onSectionChange(id)}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.98 }}
          >
            {label}
          </motion.button>
        ))}
      </nav>

      <div className="topnav-center">
        {section === "selected" || section === "all" ? (
          <div className="aihot-search">
            <Search size={16} />
            <input
              value={filters.q}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="搜索标题/摘要..."
            />
          </div>
        ) : null}
      </div>

      <div className="topnav-right">
        <div className="theme-switcher" role="group" aria-label="主题切换" data-active={theme}>
          <button
            type="button"
            className={theme === "dark" ? "theme-dot active" : "theme-dot"}
            aria-label="深色模式"
            onClick={() => onThemeChange("dark")}
          >
            <Moon size={16} />
          </button>
          <button
            type="button"
            className={theme === "system" ? "theme-dot active" : "theme-dot"}
            aria-label="跟随系统"
            onClick={() => onThemeChange("system")}
          >
            <Monitor size={16} />
          </button>
          <button
            type="button"
            className={theme === "light" ? "theme-dot active" : "theme-dot"}
            aria-label="浅色模式"
            onClick={() => onThemeChange("light")}
          >
            <Sun size={16} />
          </button>
        </div>

        {!hideLoginControls && (
          <button type="button" className="login-link" onClick={onLoginClick}>
            <LockKeyhole size={16} />后台入口
          </button>
        )}
      </div>
    </header>
  );
}
