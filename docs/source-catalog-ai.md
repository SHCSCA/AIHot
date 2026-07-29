# AI 扩展信源目录

## 目标与边界

`channels/catalogs/ai_expansion.yaml` 是 AI 频道的生产扩展目录。
目录内每个 endpoint 都声明为 `enabled: true`、`collection_status: collectable`、
`free_access: true`，但不包含 `crawl_interval_minutes`；抓取周期必须由频道级全局策略统一注入。

当前 `load_channel_configs()` 由 `channels/ai.yaml` 的 `source_catalogs` 显式合并本目录，
并从 `config/collection.yaml` 注入全局抓取周期。部署执行 `seed-sources` 后，
这些信源进入数据库调度；不得把周期重新下放到单个 source。

## 规模

- 现有 `channels/ai.yaml`：20 个 `enabled + collectable` endpoint。
- 本扩展目录：320 个 `enabled + collectable` endpoint。
- 合并且按 URL 去重后的生产配置规模：340 个，超过 320 个目标。
- 扩展构成：287 个 GitHub `releases.atom`，33 个研究、厂商、媒体或商业化 RSS/Atom。
- 唯一发布方标识：282 个 `publisher_key`。

## Schema 契约

每个 `sources[]` 条目沿用现有 source 字段，并增加目录治理元数据：

- 必填运行字段：`id`、`source_type`、`name`、`url`、`language`、`region`、
  `trust_level`、`base_weight`、`default_categories`、`parser_type`、`enabled`。
- 必填治理字段：`publisher_key`、`source_group`、`collection_status`、`free_access`。
- 禁止字段：`crawl_interval_minutes`。周期只允许由频道级策略注入。
- `parser_type` 当前统一为 `rss`。仓库的 `RssFetchAdapter` 使用 `feedparser`，
  同时支持 RSS 与 Atom；当前没有独立的 `atom` adapter 名称。
- `publisher_key` 表示发布组织或发布者，而不是单个 endpoint。
  一个发布方可以拥有多个 repo/feed。

## 分布

### Source Group

| 分组 | 数量 |
| --- | ---: |
| `open_source` | 144 |
| `developer_tools` | 125 |
| `research_institution` | 19 |
| `model_vendor` | 18 |
| `industry_media` | 14 |

### Parser / Source Type

| 类型 | 数量 |
| --- | ---: |
| `parser_type: rss` | 320 |
| `source_type: rss` | 320 |

GitHub 的 `releases.atom` 也由 `rss` parser 处理。

### Default Categories

一个 endpoint 可以覆盖多个分类，因此合计大于目录条目数。

| 分类 | endpoint 覆盖数 |
| --- | ---: |
| `ai_models` | 278 |
| `industry` | 157 |
| `agent_tools` | 133 |
| `ai_products` | 89 |
| `papers` | 23 |
| `monetization` | 6 |

### 主要发布方

完整归属以 YAML 的 `publisher_key` 为准。目录共有 282 个唯一发布方，
以下是 endpoint 数量大于 1 的主要发布方：

| Publisher Key | endpoint 数量 |
| --- | ---: |
| `research:arxiv` | 8 |
| `github_org:huggingface` | 6 |
| `github_org:microsoft` | 5 |
| `github_user:lucidrains` | 5 |
| `github_org:paddlepaddle` | 4 |
| `github_org:stability-ai` | 3 |
| `github_org:langchain-ai` | 2 |
| `github_org:ultralytics` | 2 |
| `github_org:bentoml` | 2 |
| `github_org:tensorflow` | 2 |
| `github_org:lightning-ai` | 2 |
| `github_org:ai4finance-foundation` | 2 |
| `github_user:ymcui` | 2 |
| `github_org:google` | 2 |
| `github_org:stanfordnlp` | 2 |
| `github_user:peterl1n` | 2 |
| `github_org:nvlabs` | 2 |
| `github_org:bigscience-workshop` | 2 |
| `github_org:google-deepmind` | 2 |

## 联网验证

验证日期：2026-07-28。

### GitHub release feeds

1. 使用 GitHub 官方 Search API，围绕 machine learning、deep learning、LLM、
   generative AI、Agent、RAG、MLOps、向量数据库、推理、CV、NLP、语音和 OCR
   等主题采集候选。
2. 搜索得到 2,446 条原始结果、1,737 个唯一仓库。
3. 剔除 fork、archived、低星、教程、awesome、list 和 dataset 类仓库，
   并优先选择 2025 年前创建的成熟项目。
4. 对候选 `https://github.com/<owner>/<repo>/releases.atom` 发起真实 GET。
   只有 HTTP 200、`feedparser` 非 bozo、至少一条 entry 的 feed 才进入有效池。
5. 有效池为 860 个，最终按领域覆盖、成熟度和发布方去重选择 287 个。

### RSS/Atom feeds

- 对 49 个研究机构、厂商、开发工具和产业媒体候选进行真实 GET +
  `feedparser` 校验。
- 仅保留 HTTP 200 且至少一条可解析 entry 的 33 个 endpoint。
- 被排除的 endpoint 包括 401/403/404、返回 HTML、空 feed 和 parser bozo。
- 目录中没有 Google/Bing News 查询、站内搜索结果页、同一 feed 参数变体，
  也没有为凑数构造的 URL。

本次对最终入选的 320 个 endpoint 全部执行过联网解析校验，不只是抽样。

## 风险与上线建议

- 网络验证是 2026-07-28 的快照；发布方可能迁移 feed、启用 WAF 或停止发布，
  生产仍需持续健康检查。
- GitHub release feed 可证明 endpoint 可采集，但不能保证每 12 小时都有新 release。
  新鲜度应按发布方实际节奏评估，不能把“无新条目”误判为抓取失败。
- 当前 RSS adapter 每次最多接收 5 条并按频道滚动窗口过滤；高频 arXiv feed
  可能发生截断，上线前应评估分页和窗口策略。
- `publisher_key` 是交叉验证的发布方独立性边界。交叉验证计数应按不同
  `publisher_key`，不能把同一 GitHub 组织的多个 repo 当成多个独立证据。
- 接入方式应在 `channels/ai.yaml` 声明
  `source_catalogs: [catalogs/ai_expansion.yaml]`，由 loader 合并并应用
  `config/collection.yaml`；本目录自身必须继续禁止周期字段。
- 建议分批导入：研究/官方源、核心模型与 Agent 工具、长尾开源 release、
  产业媒体。每批观察成功率、重复率和噪声率后再扩大。

## 本地结构校验

PowerShell：

```powershell
$env:PYTHONPATH = "src"
@'
from pathlib import Path
from collections import Counter
import yaml

catalog = yaml.safe_load(
    Path("channels/catalogs/ai_expansion.yaml").read_text(encoding="utf-8")
)
existing = yaml.safe_load(Path("channels/ai.yaml").read_text(encoding="utf-8"))
sources = catalog["sources"]
existing_urls = {
    source["url"].rstrip("/").lower()
    for source in existing["sources"]
}
urls = [source["url"].rstrip("/").lower() for source in sources]
required = {
    "id", "source_type", "name", "url", "language", "region",
    "trust_level", "base_weight", "default_categories", "parser_type",
    "enabled", "publisher_key", "source_group", "collection_status",
    "free_access",
}

assert len(sources) >= 300
assert len({source["id"] for source in sources}) == len(sources)
assert len(urls) == len(set(urls))
assert not (set(urls) & existing_urls)
assert all(required <= set(source) for source in sources)
assert all("crawl_interval_minutes" not in source for source in sources)
assert all(
    source["parser_type"] in {"rss", "html_list", "aihot_api"}
    for source in sources
)
assert all(
    source["enabled"]
    and source["collection_status"] == "collectable"
    and source["free_access"]
    for source in sources
)

print("sources", len(sources))
print("publishers", len({source["publisher_key"] for source in sources}))
print("groups", Counter(source["source_group"] for source in sources))
'@ | .\.venv\Scripts\python.exe -
```

联网复验应使用与生产一致的 `httpx` + `feedparser`：对每个 URL 执行 GET，
检查 HTTP 200、至少一条 entry，并记录最终 URL、content-type、bozo 和失败原因。
为避免对外站造成突发压力，建议并发不超过 12，失败最多重试一次。
