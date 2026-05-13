---
name: ai-amazon-intel
description: 查询 AI 与 Amazon 卖家情报平台的公开事件、日报和 RSS 输出
---

# AI / Amazon 情报 Skill

## 使用边界

本 Skill 只读取公开发布资产，不触发抓取、评分、聚类或数据库写入。

## 默认查询

- 用户问“最新 AI 情报”时，调用 `GET /api/v1/public/events?channel=ai&mode=selected`。
- 用户问“最新 Amazon 卖家情报”时，调用 `GET /api/v1/public/events?channel=amazon&mode=selected`。
- 用户明确说“全部”时，使用 `mode=all`。
- 用户明确说“日报”时，调用 `GET /api/v1/public/daily`。
- RSS 订阅使用 `/feed/ai/events.xml`、`/feed/ai/daily.xml`、`/feed/amazon/events.xml`、`/feed/amazon/daily.xml`。

## 输出格式

默认使用中文 Markdown：

- 标题
- 来源
- 时间
- 摘要
- 为什么值得关注
- 建议动作

不要展示内部策略版本、阈值、embedding、原始模型 JSON 或后台备注。
