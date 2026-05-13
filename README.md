# 情报引擎

这是一个 AI + Amazon 卖家情报平台，按生产级公开信源情报系统设计。

## 项目定位

本项目把公开信息源转成可检索、可解释、可分发、可回测的中文情报资产。

频道：

- `ai`：AI 模型、AI 产品、Agent 工具、论文、行业动态、商业化案例。
- `amazon`：亚马逊卖家运营、账号健康、FBA/物流、广告/PPC、Listing/SEO、费用、选品、工具、合规、税务和贸易变化。

项目采用生产级情报流水线：

```text
Source Registry
  -> Scheduler
  -> Fetch Workers
  -> Raw Documents
  -> Normalizer
  -> PreScreener
  -> LLM Score / Translation
  -> Rank Policy
  -> Event Cluster
  -> Web / RSS / API / Skill / Daily Digest
```

工程分工采用 `脚本和服务 > Skill > Agent`：

- 脚本和服务负责确定性流程。
- Skill 负责受控查询和格式化。
- Agent 负责开放式分析和策略推理。

## 安全边界

本项目不做账号登录、邮箱验证码/OTP 读取、浏览器授权、私有后台访问、第三方账号挂载等自动化。系统只处理公开信源和明确授权 API。

## 本地安装

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

## 运行测试

```powershell
.\.venv\Scripts\python -m pytest -v
```

## 启动 API

```powershell
.\.venv\Scripts\python -m uvicorn intel_engine.main:app --host 127.0.0.1 --port 8000
```

生产库通过环境变量接入：

```powershell
$env:DATABASE_URL="<cloud-postgres-url>"
$env:ADMIN_USERNAME="admin"
$env:ADMIN_PASSWORD="<strong-password>"
$env:LLM_PROVIDER="deepseek"
$env:LLM_MODEL="deepseek-v4-flash"
$env:DEEPSEEK_API_KEY="<deepseek-api-key>"
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\intel-engine seed-sources
.\.venv\Scripts\intel-engine pipeline-once
```

如果不设置 `LLM_PROVIDER`，系统默认继续使用 `fake`，便于测试和本地稳定回归。启用 DeepSeek 后，模型只负责输出结构化多维评分、中文标题、中文摘要和推荐理由；最终是否精选仍由 `RankPolicy` 的确定性公式决定。

常用端点：

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/api/public/channels
http://127.0.0.1:8000/api/public/items?channel=ai&take=20
http://127.0.0.1:8000/api/v1/public/events?channel=ai
http://127.0.0.1:8000/api/v1/public/daily?channel=ai
http://127.0.0.1:8000/feed/ai/events.xml
http://127.0.0.1:8000/feed/ai/daily.xml
http://127.0.0.1:8000/admin
```

## 当前已实现能力

- 频道配置加载：`channels/ai.yaml`、`channels/amazon.yaml`
- 可解释评分模型：`src/intel_engine/scoring.py`
- RSS/网页公开内容解析：`src/intel_engine/crawler.py`
- 条目规范化和内容 hash：`src/intel_engine/normalizer.py`
- 过渡期 SQLite 存储和 hash 去重：`src/intel_engine/storage.py`
- 入库流程：`src/intel_engine/ingest.py`
- 公开 API：`/health`、`/api/public/channels`、`/api/public/items`
- 生产数据库模型：`sources`、`fetch_jobs`、`raw_documents`、`normalized_items`、`strategy_versions`、`event_clusters`、`daily_digests` 等
- Source Registry 和 seed 导入：`src/intel_engine/sources.py`、`src/intel_engine/source_seed.py`
- 调度和 job queue：`src/intel_engine/scheduler.py`
- Fetch Adapter 和 Raw Store：`src/intel_engine/fetchers/`、`src/intel_engine/raw_store.py`
- 预筛、模型中间量和确定性排序策略：`src/intel_engine/prescreen.py`、`src/intel_engine/llm.py`、`src/intel_engine/rank_policy.py`
- LLM Provider：默认 `fake`，已支持 `deepseek`，可通过 `LLM_PROVIDER`、`LLM_MODEL`、`DEEPSEEK_API_KEY` 切换
- 事件聚类：`src/intel_engine/clustering.py`
- v1 公开发布 API、RSS 和 Skill：`/api/v1/public/events`、`/api/v1/public/daily`、`src/intel_engine/rss.py`、`skills/ai-amazon-intel/SKILL.md`
- 内部运营 API：`/api/v1/internal/sources`、`/api/v1/internal/source-states`、`/api/v1/internal/jobs`、`/api/v1/internal/strategy-versions`、`/api/v1/internal/feedback-events`、`/api/v1/internal/evaluation-runs`
- Basic Auth 后台鉴权：`ADMIN_USERNAME`、`ADMIN_PASSWORD`
- Pipeline worker 闭环：`src/intel_engine/pipeline.py`
- 日报生成和策略评估：`src/intel_engine/daily.py`、`src/intel_engine/evaluation.py`
- React 运营后台：`web/`

## 生产目标技术栈

- Python 3.12+
- FastAPI + Pydantic v2
- PostgreSQL 16+ + SQLAlchemy 2 + Alembic
- pgvector
- httpx / feedparser / trafilatura
- Postgres job table + `FOR UPDATE SKIP LOCKED`
- Docker Compose 起步，后续可拆分 worker 和调度器

## 文档

- `docs/PRODUCT_SPEC.md`
- `docs/ARCHITECTURE.md`
- `docs/API.md`
- `docs/AIHOT_SYSTEM_DEEP_READING.md`
- `docs/AIHOT_ARTICLE_DEEP_DIVE.md`
- `docs/superpowers/plans/2026-05-11-production-intelligence-platform.md`
- `docs/superpowers/plans/2026-05-11-intelligence-engine-mvp.md`
