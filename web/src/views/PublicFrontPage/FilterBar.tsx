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
    <section className="aihot-filter-panel liquid-glass-subtle" data-channel={channel}>
      <div className="filter-groups" aria-label="信源和分类筛选">
        <div className="filter-group filter-group-source" aria-label="信源筛选">
          <span className="filter-group-title">信源</span>
          <div className="filter-pill-row">
            {sourceGroups.map((option) => (
              <motion.button
                key={option.value || "all"}
                className={filters.sourceGroup === option.value ? "active" : ""}
                aria-pressed={filters.sourceGroup === option.value}
                onClick={() => onChange({ sourceGroup: option.value })}
                whileHover={{ y: -1 }}
                whileTap={{ scale: 0.98 }}
              >
                {filters.sourceGroup === option.value && <motion.span className="filter-pill-liquid" layoutId="filter-source-liquid" />}
                <span>{option.label}</span>
              </motion.button>
            ))}
          </div>
        </div>

        <div className="filter-group filter-group-category" aria-label="分类筛选">
          <span className="filter-group-title">分类</span>
          <div className="filter-pill-row">
            <motion.button
              className={filters.category === "" ? "active" : ""}
              aria-pressed={filters.category === ""}
              onClick={() => onChange({ category: "" })}
              whileHover={{ y: -1 }}
              whileTap={{ scale: 0.98 }}
            >
              {filters.category === "" && <motion.span className="filter-pill-liquid" layoutId="filter-category-liquid" />}
              <span>全部分类</span>
            </motion.button>
            {categories.map((option) => (
              <motion.button
                key={option.value}
                className={filters.category === option.value ? "active" : ""}
                aria-pressed={filters.category === option.value}
                onClick={() => onChange({ category: option.value })}
                whileHover={{ y: -1 }}
                whileTap={{ scale: 0.98 }}
              >
                {filters.category === option.value && <motion.span className="filter-pill-liquid" layoutId="filter-category-liquid" />}
                <span>{option.shortLabel ?? option.label}</span>
              </motion.button>
            ))}
          </div>
        </div>
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
