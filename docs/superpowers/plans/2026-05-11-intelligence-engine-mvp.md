# 情报引擎 MVP 实施计划

> 历史计划：本计划记录早期 MVP 验证过程。项目现已切换为生产级架构基线，后续执行以 `docs/superpowers/plans/2026-05-11-production-intelligence-platform.md` 为准。

> **给自动化执行者：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐项执行本计划。步骤使用复选框语法，便于跟踪。

**目标：** 构建 AI + Amazon 卖家情报引擎第一版，包含频道配置、评分、公开 API 骨架、测试，以及后续抓取、日报、RSS、Agent Skill 的扩展点。

**架构：** 用 Python 确定性核心处理配置、评分、API 结构和后续抓取/存储。频道分类和信源放在 `channels/*.yaml`，FastAPI 应用入口放在 `src/intel_engine/main.py`。

**技术栈：** Python 3.11+、FastAPI、Pydantic、PyYAML、pytest、SQLite，后续通过 SQLAlchemy 管理持久化。

---

## 文件结构

- `docs/PRODUCT_SPEC.md`：产品范围、不做事项、频道定义、评分模型和 MVP 边界。
- `docs/ARCHITECTURE.md`：系统分层、数据模型、处理流程和安全边界。
- `docs/API.md`：公开 API 响应契约。
- `channels/ai.yaml`：AI 频道分类、权重和初始公开信源。
- `channels/amazon.yaml`：Amazon 卖家频道分类、权重和初始公开信源。
- `pyproject.toml`：Python 包元数据、运行依赖和 pytest 配置。
- `src/intel_engine/__init__.py`：包标记和版本。
- `src/intel_engine/channel_config.py`：加载并校验频道 YAML。
- `src/intel_engine/scoring.py`：加权评分和 Amazon 卖家行动等级。
- `src/intel_engine/routes.py`：公开 API 路由。
- `src/intel_engine/main.py`：FastAPI 应用工厂和 ASGI app。
- `tests/test_channel_config.py`：验证频道配置加载。
- `tests/test_scoring.py`：验证评分模型。
- `tests/test_api.py`：验证健康检查和频道 API。

## 任务 1：基础文档

**文件：**
- 创建：`docs/PRODUCT_SPEC.md`
- 创建：`docs/ARCHITECTURE.md`
- 创建：`docs/API.md`

- [x] **步骤 1：编写产品规格**

创建 `docs/PRODUCT_SPEC.md`，说明 AI + Amazon 卖家情报范围、公开数据边界、频道分类和评分模型。

- [x] **步骤 2：编写架构文档**

创建 `docs/ARCHITECTURE.md`，说明确定性核心、LLM 处理能力、Agent 接口、数据模型和处理流程。

- [x] **步骤 3：编写 API 草案**

创建 `docs/API.md`，说明 `/health`、`/api/public/channels`、`/api/public/items` 和 `/api/public/daily` 响应契约。

## 任务 2：Python 项目骨架

**文件：**
- 创建：`pyproject.toml`
- 创建：`src/intel_engine/__init__.py`
- 创建：`src/intel_engine/main.py`
- 创建：`src/intel_engine/routes.py`

- [x] **步骤 1：添加包元数据**

创建 `pyproject.toml`，包含 FastAPI、PyYAML、httpx、feedparser、SQLAlchemy 和 pytest 依赖。

- [x] **步骤 2：添加应用工厂**

`src/intel_engine/main.py` 暴露：

```python
from fastapi import FastAPI

from intel_engine.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="Intelligence Engine", version="0.1.0")
    app.include_router(router)
    return app


app = create_app()
```

- [x] **步骤 3：添加基础路由**

`src/intel_engine/routes.py` 暴露 `/health` 和 `/api/public/channels`。

## 任务 3：频道配置

**文件：**
- 创建：`channels/ai.yaml`
- 创建：`channels/amazon.yaml`
- 创建：`src/intel_engine/channel_config.py`
- 创建：`tests/test_channel_config.py`

- [x] **步骤 1：编写频道 YAML**

每个频道文件定义：

```yaml
id: ai
name: AI 情报
description: 频道描述
categories:
  - id: ai_models
    label: 模型发布
scoring:
  selected_threshold: 75
sources:
  - id: openai_blog
    name: OpenAI Blog
    url: https://openai.com/news/
```

- [x] **步骤 2：实现配置加载器**

`load_channel_configs()` 读取 `channels/` 下所有 `*.yaml` 文件，并返回 `ChannelConfig` 对象。

- [x] **步骤 3：测试配置加载**

运行：

```powershell
python -m pytest tests/test_channel_config.py -v
```

期望：`ai` 和 `amazon` 都能加载分类和信源。

## 任务 4：评分核心

**文件：**
- 创建：`src/intel_engine/scoring.py`
- 创建：`tests/test_scoring.py`

- [x] **步骤 1：添加加权评分函数**

实现 `calculate_final_score()`。

- [x] **步骤 2：添加卖家行动等级函数**

实现 `seller_action_level(final_score, impact_score, actionability_score)`，返回 `watch`、`review`、`act_soon` 或 `urgent`。

- [x] **步骤 3：测试评分**

运行：

```powershell
python -m pytest tests/test_scoring.py -v
```

期望：综合分稳定，高影响 Amazon 条目会被标为 `urgent`。

## 任务 5：API 验证

**文件：**
- 创建：`tests/test_api.py`
- 修改：`src/intel_engine/routes.py`

- [x] **步骤 1：测试健康检查**

用 FastAPI `TestClient` 断言 `/health` 返回 `{"status": "ok", "service": "intel-engine"}`。

- [x] **步骤 2：测试频道端点**

断言 `/api/public/channels` 返回 `ai` 和 `amazon` 频道元数据。

- [x] **步骤 3：运行完整测试**

运行：

```powershell
python -m pytest -v
```

期望：所有测试通过。

## 任务 6：第二阶段里程碑

**即将新增文件：**
- `src/intel_engine/storage.py`
- `src/intel_engine/crawler.py`
- `src/intel_engine/normalizer.py`
- `src/intel_engine/dedupe.py`
- `src/intel_engine/ingest.py`
- `tests/test_storage.py`
- `tests/test_crawler.py`
- `tests/test_normalizer.py`
- `tests/test_ingest.py`

执行顺序：

1. [x] SQLite schema 和 repository。
2. [x] RSS/网页抓取器。
3. [x] 条目规范化和 hash 去重。
4. [x] 入库流程。
5. [x] `/api/public/items` 查询。
6. [ ] 日报、RSS 和 Agent Skill。

## 自检

- 规格覆盖：产品范围、架构、API、频道配置、评分和测试均已覆盖。
- 占位符检查：没有依赖未命名函数或未指定文件。
- 类型一致性：路由名、配置字段和评分函数在任务中保持一致。
