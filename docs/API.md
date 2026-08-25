# 生产 API 规格

API 分为两组：

- Public API：对 Web、RSS、Skill、外部集成开放，只读、字段稳定。
- Internal API：给后台和策略运营使用，需要认证、审计和权限控制。

截至 2026-06-17，代码同时包含兼容用 `/api/public/*`、正式 `/api/v1/public/*`、认证 `/api/v1/auth/*` 和运营 `/api/v1/internal/*`。本文记录当前主要契约和生产约束；新增前端功能不得绕过这些 API 直接访问数据库。

## API 原则

- 版本前缀使用 `/api/v1`。
- 公开 API 不暴露内部策略字段。
- 列表接口使用 cursor 分页。
- 所有时间使用 ISO 8601。
- 所有公开内容默认中文字段优先。
- OpenAPI schema 必须可被 Agent 和 SDK 使用。
- 请求必须带合理 `User-Agent`。

## 健康检查

```http
GET /health
```

响应：

```json
{
  "status": "ok",
  "service": "intel-engine"
}
```

## 频道列表

```http
GET /api/v1/public/channels
```

响应：

```json
{
  "channels": [
    {
      "id": "ai",
      "name": "AI 情报",
      "description": "AI 模型、产品、Agent、论文、行业和商业化动态"
    },
    {
      "id": "amazon",
      "name": "Amazon 卖家情报",
      "description": "亚马逊电商、卖家运营、跨境卖货风险和机会"
    }
  ]
}
```

## 情报事件列表

生产 API 默认返回事件簇，而不是裸条目。

```http
GET /api/v1/public/events?channel=ai&mode=selected&window=24h&take=20
```

查询参数：

```text
channel: ai | amazon
mode: selected | all
category: 可选频道分类
q: 可选关键词
window: 24h | 3d | 7d | 自定义 from/to
take: 1-100，默认 20
cursor: 可选分页游标
```

响应：

```json
{
  "count": 1,
  "hasNext": false,
  "nextCursor": null,
  "events": [
    {
      "id": "evt_001",
      "channel": "amazon",
      "title": "示例事件标题",
      "summary": "中文摘要",
      "category": "account_health",
      "firstSeenAt": "2026-05-11T00:00:00Z",
      "lastSeenAt": "2026-05-11T02:00:00Z",
      "score": 86.5,
      "entryReason": "为什么值得看",
      "suggestedAction": "建议卖家做什么",
      "sellerActionLevel": "review",
      "sourceCount": 3,
      "mainSource": {
        "name": "Example Source",
        "url": "https://example.com/article"
      }
    }
  ]
}
```

## 事件详情

```http
GET /api/v1/public/events/{event_id}
```

响应：

```json
{
  "id": "evt_001",
  "channel": "ai",
  "title": "示例事件标题",
  "summary": "中文摘要",
  "category": "model_release",
  "score": 91.2,
  "entryReason": "为什么值得看",
  "relatedSources": [
    {
      "title": "官方公告标题",
      "source": "Official Blog",
      "url": "https://example.com/official",
      "publishedAt": "2026-05-11T00:00:00Z",
      "isMain": true
    }
  ]
}
```

## 条目列表

裸条目接口保留给调试和高级用户，不作为默认消费入口。

```http
GET /api/v1/public/items?channel=ai&mode=selected&take=20
```

## 公开信源

Reader Mode 的信源墙使用公开信源接口，不暴露内部备注和策略细节。

```http
GET /api/v1/public/sources?channel=ai&sourceGroup=social&page=1&pageSize=20
```

## 公共反馈

公共反馈表单写入反馈事件，供 Ops Mode 继续处理。

```http
POST /api/v1/public/feedback-events
```

## 日报

```http
GET /api/v1/public/daily?channel=ai
GET /api/v1/public/daily/{YYYY-MM-DD}?channel=amazon
GET /api/v1/public/dailies?channel=ai&take=30
```

响应：

```json
{
  "channel": "amazon",
  "date": "2026-05-11",
  "generatedAt": "2026-05-11T08:00:00+08:00",
  "sections": [
    {
      "id": "account_health",
      "label": "账号风控",
      "items": [
        {
          "eventId": "evt_001",
          "title": "示例标题",
          "summary": "摘要",
          "sourceUrl": "https://example.com/article",
          "sourceName": "Example Source",
          "suggestedAction": "检查当前 Listing 和账号健康指标"
        }
      ]
    }
  ]
}
```

## RSS

```text
GET /feed/ai.xml
GET /feed/ai/all.xml
GET /feed/ai/daily.xml
GET /feed/amazon.xml
GET /feed/amazon/all.xml
GET /feed/amazon/daily.xml
```

RSS 只消费已发布事件和日报，不触发实时抓取。

## Skill 查询模式

Skill 使用 Public API，不直接访问数据库。

支持：

```text
get_daily(channel, date?)
get_dailies(channel, window?)
get_events(channel, mode, category?, window?, q?)
get_event(event_id)
```

默认行为：

- 未指定 `mode` 时使用 `selected`。
- 未指定窗口时使用过去 24 小时。
- 用户明确说“全部”才使用 `all`。
- 用户明确说“日报”才调用 daily。

## Internal API

内部 API 使用 RBAC 权限过滤，服务于 Ops Mode 和 Lab Mode。

主要端点：

```text
POST /api/v1/auth/login
POST /api/v1/auth/logout
GET /api/v1/me
PATCH /api/v1/me/preferences
GET /api/v1/internal/dashboard
GET /api/v1/internal/quality-dashboard
GET /api/v1/internal/sources
POST /api/v1/internal/sources
PATCH /api/v1/internal/sources/{source_id}
GET /api/v1/internal/source-states
GET /api/v1/internal/source-diagnostics
GET /api/v1/internal/jobs
POST /api/v1/internal/jobs/{job_id}/retry
GET /api/v1/internal/strategy-versions
POST /api/v1/internal/strategy-versions
POST /api/v1/internal/strategy-versions/{strategy_id}/activate
POST /api/v1/internal/evaluation-runs
GET /api/v1/internal/evaluation-runs
GET /api/v1/internal/evaluation-runs/{run_id}
POST /api/v1/internal/evaluation-runs/{run_id}/run
POST /api/v1/internal/feedback-events
GET /api/v1/internal/feedback-events
PATCH /api/v1/internal/feedback-events/{feedback_id}
GET /api/v1/internal/events
GET /api/v1/internal/events/{event_id}
PATCH /api/v1/internal/events/{event_id}/review
GET /api/v1/internal/daily-digests
POST /api/v1/internal/daily-digests/generate
POST /api/v1/internal/daily-digests/{digest_id}/publish
POST /api/v1/internal/daily-digests/{digest_id}/unpublish
GET /api/v1/internal/users
POST /api/v1/internal/users
PATCH /api/v1/internal/users/{user_id}
GET /api/v1/internal/roles
PATCH /api/v1/internal/roles/{role_id}
GET /api/v1/internal/audit-logs
GET /api/v1/internal/pipeline-runs
POST /api/v1/internal/pipeline-runs
GET /api/v1/internal/system-settings
PATCH /api/v1/internal/system-settings
```

系统设置接口需要 `system.manage` 权限。`aiAnalysisEnabled=true` 时流水线使用当前环境配置的 AI provider；关闭后使用 `rules-v1` 完成初筛、评分和确定性交叉验证，不会发起 AI provider 请求。切换动作写入操作审计。

内部 API 认证和初始化账号来自环境变量：

```text
ADMIN_USERNAME
ADMIN_PASSWORD
```

认证 API 会创建会话，前端按 `/api/v1/me` 返回的 roles 和 permissions 过滤后台导航。旧 Basic Auth 语义仍是服务端认证边界的一部分，但前端以登录会话为主。

Lab Mode 只使用 `strategy-versions` 和 `evaluation-runs` 现有字段。若 UI 需要更细的回测指标、成本拆分或样本级对比，应先扩展后端契约，不能在前端 mock。

RSS 输出：

```text
GET /feed/{channel}/events.xml
GET /feed/{channel}/daily.xml
```
