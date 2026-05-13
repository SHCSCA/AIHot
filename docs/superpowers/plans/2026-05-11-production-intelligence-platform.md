# 生产级情报平台实施计划

## 目标

把当前过渡 MVP 改造成生产级公开信源情报平台：

```text
Source Registry
  -> Scheduler
  -> Pipeline
  -> Strategy Versioning
  -> Event Cluster
  -> Publisher
```

本计划以生产标准为目标，不再以 SQLite 抓取脚本作为目标架构。

## 阶段 0：规格冻结

- [x] 更新 `docs/PRODUCT_SPEC.md` 为生产级产品规格。
- [x] 更新 `docs/ARCHITECTURE.md` 为生产级架构。
- [x] 更新 `docs/API.md` 为生产 API 规格。
- [x] 更新 `pyproject.toml` 的生产依赖基线。
- [x] 更新 `README.md` 的项目定位。

## 阶段 1：数据库和迁移

目标：让 PostgreSQL 成为正式主库。

文件范围：

- `alembic.ini`
- `migrations/`
- `src/intel_engine/settings.py`
- `src/intel_engine/db.py`
- `src/intel_engine/models.py`

任务：

- [x] 新增 Pydantic Settings，读取 `DATABASE_URL`。
- [x] 新增 SQLAlchemy engine/session 管理。
- [x] 接入 Alembic。
- [x] 建立首批生产表：
  - `sources`
  - `source_states`
  - `fetch_jobs`
  - `fetch_runs`
  - `raw_documents`
  - `normalized_items`
  - `prefilter_results`
  - `model_scores`
  - `ranked_items`
  - `event_clusters`
  - `cluster_members`
  - `strategy_versions`
  - `feedback_events`
  - `daily_digests`
  - `evaluation_runs`
- [x] 保留 SQLite 仅用于轻量单元测试。

验证：

- [x] Alembic migration 已在空 SQLite 验证库执行；空 PostgreSQL 需本机提供 PostgreSQL/Docker 后复验。
- [x] 测试库能初始化并回滚。

## 阶段 2：Source Registry

目标：把 `channels/*.yaml` 从运行配置降级为 seed 配置。

文件范围：

- `src/intel_engine/sources.py`
- `src/intel_engine/source_seed.py`
- `tests/test_sources.py`

任务：

- [x] 实现 `SourceRegistry`。
- [x] 实现 source seed 导入。
- [x] 支持 source tier、adapter、interval、priority、visibility。
- [x] 支持 source state 更新。

验证：

- [x] seed 可重复导入且幂等。
- [x] 单个 source 可启停、降频、更新状态。

## 阶段 3：Scheduler 和 Job Queue

目标：用 PostgreSQL job table 替代顺序扫全量。

文件范围：

- `src/intel_engine/scheduler.py`
- `src/intel_engine/jobs.py`
- `tests/test_scheduler.py`

任务：

- [x] Scheduler 根据 `source_states.next_fetch_at` 生成 `fetch_jobs`。
- [x] Worker 使用 `FOR UPDATE SKIP LOCKED` 领取任务。
- [x] 支持失败重试和 backoff。
- [x] 支持 job 幂等。

验证：

- [x] 多 worker 不重复领取同一 job。
- [x] 一个信源失败不影响其他信源。

## 阶段 4：Fetch Adapter 和 Raw Store

目标：把抓取和解析变成可扩展 adapter。

文件范围：

- `src/intel_engine/fetchers/`
- `src/intel_engine/raw_store.py`
- `tests/test_fetchers.py`

任务：

- [x] 定义 `FetchAdapter` 接口。
- [x] 实现 RSS adapter。
- [x] 实现 HTTP article adapter。
- [x] 接入 trafilatura。
- [x] 保存 `raw_documents` 和 `fetch_runs`。

验证：

- [x] 同一 URL 重复抓取可去重。
- [x] fetch metadata 可追踪。

## 阶段 5：PreScreener、LLMEnricher、RankPolicy

目标：拆开 LLM 中间量和确定性策略。

文件范围：

- `src/intel_engine/prescreen.py`
- `src/intel_engine/llm.py`
- `src/intel_engine/rank_policy.py`
- `tests/test_rank_policy.py`

任务：

- [x] 定义预筛 schema。
- [x] 定义模型评分 schema。
- [x] 实现无 LLM 的 fake provider，用于测试。
- [x] 实现确定性 `RankPolicy`。
- [x] 支持策略版本和阈值。

验证：

- [x] LLM 输出不直接决定精选。
- [x] 不同 source tier 和 category threshold 能影响最终分。

## 阶段 6：Event Cluster

目标：输出事件，而不是重复条目。

文件范围：

- `src/intel_engine/clustering.py`
- `tests/test_clustering.py`

任务：

- [x] 精确 URL/hash 去重。
- [x] 标题近似去重。
- [x] pgvector embedding 接口预留。
- [x] 主条选择按来源权威度排序。

验证：

- [x] 同事件多来源归为一个 cluster。
- [x] 官方源优先成为 main item。

## 阶段 7：Publisher

目标：Web/API/RSS/Skill 消费同一份情报资产。

文件范围：

- `src/intel_engine/routes.py`
- `src/intel_engine/rss.py`
- `skills/ai-amazon-intel/SKILL.md`

任务：

- [x] `/api/v1/public/events`
- [x] `/api/v1/public/events/{id}`
- [x] `/api/v1/public/daily`
- [x] RSS feed。
- [x] Skill 文档和查询约定。

验证：

- [x] 发布层不触发重新抓取或重新评分。
- [x] Public API 不泄露内部策略字段。

## 阶段 8：运营后台基础

目标：支持信源和策略长期运营。

任务：

- [x] source list。
- [x] source health。
- [x] job runs。
- [x] strategy versions。
- [x] feedback events。
- [x] evaluation runs。

此阶段可先做 internal API，再做前端。

## 验收标准

- PostgreSQL 是正式主库。
- 任一信源失败不影响整批任务。
- 每个条目能追溯到原始文档、信源、抓取任务和策略版本。
- LLM 输出和最终决策分离。
- 事件聚类在输出层生效。
- 日报/RSS/API/Skill 消费同一份情报资产。
- 公开 API 不泄露内部策略字段。
