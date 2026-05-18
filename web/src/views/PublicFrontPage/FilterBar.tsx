import { motion } from "framer-motion";
import { RefreshCw } from "lucide-react";
import type { PublicChannel } from "./index";
import type { PublicApi } from "../../api";

interface FilterBarProps {
  channel: PublicChannel;
  filters: { q: string; category: string; date: string; sourceGroup: string };
  onChange: (filters: Partial<{ category: string; date: string; sourceGroup: string }>) => void;
  onRefresh: () => void;
}

const sourceGroups = [
  { value: "", label: "全部信源" },
  { value: "official,first_party", label: "官方/一手" },
  { value: "media", label: "资讯" },
  { value: "social,community", label: "社媒/社区" }
];

interface CategoryOption {
  value: string;
  label: string;
  shortLabel: string;
}

function categoryOptions(channel: PublicChannel): CategoryOption[] {
  if (channel === "amazon") {
    return [
      { value: "policy,account_health,compliance_trade", label: "政策/账号", shortLabel: "政策/账号" },
      { value: "fba_logistics", label: "FBA/物流", shortLabel: "FBA/物流" },
      { value: "ads_ppc,listing_seo", label: "广告/Listing", shortLabel: "广告/Listing" },
      { value: "fees_margin,product_research", label: "费用/选品", shortLabel: "费用/选品" },
      { value: "tools", label: "工具", shortLabel: "工具" }
    ];
  }
  return [
    { value: "ai_models,papers", label: "模型/论文", shortLabel: "模型/论文" },
    { value: "ai_products,agent_tools", label: "产品/Agent", shortLabel: "产品/Agent" },
    { value: "industry,monetization", label: "行业/商业化", shortLabel: "行业/商业化" }
  ];
}

export function FilterBar({ channel, filters, onChange, onRefresh }: FilterBarProps) {
  const categories = categoryOptions(channel);

  return (
    <section className="aihot-filter-panel">
      <div className="filter-capsules" aria-label="信源和分类筛选">
        <span className="filter-label">信源</span>
        {sourceGroups.map((option) => (
          <motion.button
            key={option.value || "all"}
            className={filters.sourceGroup === option.value ? "active" : ""}
            onClick={() => onChange({ sourceGroup: option.value })}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            {option.label}
          </motion.button>
        ))}

        <span className="filter-divider" />

        <span className="filter-label">分类</span>
        {categories.map((option) => (
          <motion.button
            key={option.value}
            className={filters.category === option.value ? "active" : ""}
            onClick={() => onChange({ category: option.value })}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            {option.shortLabel ?? option.label}
          </motion.button>
        ))}
      </div>

      <label className="date-filter">
        <input
          type="date"
          value={filters.date}
          onChange={(e) => onChange({ date: e.target.value })}
        />
      </label>

      <motion.button
        className="ghost dark refresh-btn"
        onClick={onRefresh}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        <RefreshCw size={15} />刷新
      </motion.button>
    </section>
  );
}
