import { motion } from "framer-motion";
import { Rss } from "lucide-react";
import type { PublicChannel } from "./index";

interface RssLinksProps {
  channel: PublicChannel;
}

const feedLinks: Array<{ channel: PublicChannel; label: string; url: string; description: string }> = [
  { channel: "ai", label: "AI 事件 RSS", url: "/feed/ai/events.xml", description: "订阅 AI 热点事件流" },
  { channel: "ai", label: "AI 日报 RSS", url: "/feed/ai/daily.xml", description: "订阅 AI 每日精选" },
  { channel: "amazon", label: "亚马逊事件 RSS", url: "/feed/amazon/events.xml", description: "订阅亚马逊情报事件流" },
  { channel: "amazon", label: "亚马逊日报 RSS", url: "/feed/amazon/daily.xml", description: "订阅亚马逊每日精选" }
];

export function RssLinks({ channel }: RssLinksProps) {
  const links = feedLinks.filter((link) => link.channel === channel);

  return (
    <section className="rss-grid dark" aria-label="RSS 订阅入口">
      {links.map((link) => (
        <motion.a
          key={link.url}
          href={link.url}
          target="_blank"
          rel="noreferrer"
          className="rss-card liquid-glass-subtle"
          whileHover={{ scale: 1.03, y: -2 }}
          whileTap={{ scale: 0.98 }}
        >
          <Rss size={18} />
          <strong>{link.label}</strong>
          <span>{link.description}</span>
        </motion.a>
      ))}
    </section>
  );
}
