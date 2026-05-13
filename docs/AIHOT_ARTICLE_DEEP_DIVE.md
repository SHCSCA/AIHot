# 三篇 AIHOT 文章深度解读

## 资料范围

本解读基于本地保存的三篇微信文章 HTML：

- `C:/Users/wz/Downloads/这个封装了我3年自媒体经验的AI热点网站，今天向所有人免费开放。.html`
- `C:/Users/wz/Downloads/装了这个AI热点Skill之后，你再也不需要自己去刷AI新闻了。.html`
- `C:/Users/wz/Downloads/能用脚本就别用Agent。.html`

正文可以读取。图片方面，原始 HTML/MHTML 只内嵌了少量首屏图片，但正文里的 `data-src` 远程链接仍然可访问。已从这些链接下载 43 张图片到：

```text
data/aihot_images/
```

其中：

- `site_*.png/jpg/webp`：AIHOT 网站文章图片。
- `skill_*.png/jpg/webp`：AIHOT Skill/RSS/API 文章图片。
- `manifest.json`：下载清单。

因此，本文图片分析基于已下载图片，而不是仅按上下文推断。

## 结论先行

这三篇文章实际构成了一套完整方法论：

```text
AIHOT 网站文章：讲产品和情报处理系统。
AIHOT Skill 文章：讲数据分发和 Agent 接入。
脚本/Skill/Agent 文章：讲工程运行哲学。
```

它不是单纯的新闻站，也不是一个靠 Agent 临场搜索的工具，而是一个“公开信源情报操作系统”：

```text
信源池
  -> 抓取
  -> 低成本预筛
  -> 翻译 / 摘要 / 五维评分
  -> 确定性权重公式
  -> 分类阈值精选
  -> embedding 事件聚类
  -> 时间线 / 日报 / RSS / API / Skill
```

最核心的架构思想是：**LLM 只做语义判断，系统性决策由代码控制。**  
也就是文章里的工程哲学：能脚本化的必须脚本化，脚本处理不了但边界清楚的能力做成 Skill，只有开放式、动态规划任务才交给 Agent。

## 第一篇：AIHOT 网站的产品模式

文章标题是“这个封装了我3年自媒体经验的AI热点网站，今天向所有人免费开放。”，核心不是发布一个网站，而是解释一个信息筛选系统的形成逻辑。

### 1. 产品定位

AIHOT 解决的是“获取信息”阶段，不直接解决“分析”和“决策”阶段。

作者把自己的内容创作流程拆成：

```text
获取信息 -> 分析信息 -> 基于信息做决策
```

AIHOT 专注第一步：从信息海里筛掉低价值、重复、无关、低可信、二手转述的信息，把值得关注的内容推到用户面前。

因此它的本质不是“AI 新闻聚合站”，而是：

```text
注意力保护系统
  + 信源质量系统
  + 情报精选系统
  + 创作者选题辅助系统
```

这点对我们非常关键。我们的项目不能只做“多源抓取 + 摘要”，否则会变成普通聚合器。真正的价值在于把“什么值得看”产品化、参数化、可回测、可解释。

### 2. 信源设计

文章明确提到当前持续监控信源是 168 个，来源形式包括：

- RSS 订阅。
- HTML 直接抓取。
- 公开 API。
- 付费第三方数据接口。

信源不是简单列表，而是有质量等级：

- `T1`：最值得关注的一手信息源，例如官方博客、工程博客、重要研究机构博客。
- `T1.5`：官方社交账号，信息更快但更杂，权重低于官网。
- `T2`：个人号、KOL、媒体、综合资讯站等二手或混合信源。

这个模型说明：信源系统需要从第一天就有“权威度”和“来源类型”字段。它不是后续优化项，而是评分、聚类主条选择、精选阈值的基础。

对我们的项目，AI 和 Amazon 两个频道都应该采用同样模型：

```text
source_tier: T1 / T1.5 / T2 / T3
source_type: official_blog / official_social / docs / api / media / kol / forum / newsletter
authority_weight: 数值权重
noise_level: 噪声等级
freshness_weight: 时效权重
```

### 3. 信息漏斗

文章给出的运行规模是：100 多个信源每天会抓取几百条信息，其中某一天抓了 563 条，而且有大量内容与 AI 无关。

这说明系统不是“抓到就处理”，而是漏斗：

```text
原始抓取条目
  -> AI 相关性预筛
  -> 通过者进入后续评分和摘要
  -> 未通过者仍落库但不进入高成本处理
```

这背后有两个工程理由：

- 成本控制：便宜模型先筛，通过后才交给更强模型。
- 数据保留：无关条目不丢弃，而是落库，方便复盘信源噪声。

我们的架构也应区分：

- `raw_documents`：抓到了什么。
- `normalized_items`：规范化后的候选条目。
- `screening_results`：是否相关，为什么不相关。
- `ranked_items`：完成评分并可进入精选池的条目。

### 4. 评分系统的关键转折

文章里最重要的工程经验是：一开始试图让模型直接判断“是否值得精选”，后来发现效果越来越差。

失败路径大概是：

```text
大模型直接打最终分
  -> 加规则
  -> prompt 越来越长
  -> 人类反馈标注
  -> 自动评估
  -> 更多规则
  -> 泛化能力下降
  -> 回滚重构
```

最终方案变成：

```text
LLM 只输出多个维度分
代码根据来源、类型、公司、类别、阈值计算最终质量分
代码决定是否精选
```

这是三篇文章里最值得吸收的设计模式：

```text
LLM 负责语义感知。
代码负责政策、权重、阈值、选择。
```

对我们来说，不能让模型直接返回 `selected=true` 作为最终决策。正确方式是让模型输出结构化中间量，例如：

- 相关性分。
- 新颖性分。
- 影响程度分。
- 行动价值分。
- 信息密度分。
- 受影响对象。
- 分类。
- 一句话理由。

然后由 `RankPolicy` 统一计算：

```text
final_score =
  model_semantic_score
  * source_authority_weight
  * freshness_weight
  * category_threshold_policy
  * duplicate_penalty
  * channel_specific_impact_weight
```

精选由代码阈值决定，并且不同来源、不同类别、不同频道可以有不同阈值。

### 5. 事件聚类系统

文章明确提到，评分和精选之外，还有事件聚类系统。做法是用 embedding 把语义相近条目聚成事件簇，再从簇里选择最权威的一条当主条，其他折叠。

主条优先级大致是：

```text
官网 > 官方社交账号 > KOL / 媒体 / 综合站
```

这说明去重不是简单 URL hash。AIHOT 要解决的是“同一事件被不同信源报道多次”的问题。

我们的去重也需要三层：

- 精确去重：canonical URL、content hash。
- 近似去重：标题相似、正文指纹、simhash/minhash。
- 事件聚类：embedding 聚类，多来源归并为一个情报事件。

Amazon 频道尤其需要事件聚类。例如一个 FBA 费用调整，可能同时出现在官方公告、卖家论坛、媒体解读、服务商文章里。最终应该输出一个事件，下面挂多个来源。

### 6. 日报生成

日报不是临时让大模型重新生成。文章明确说，日报只需要把已经处理好的精选、分类、翻译结果按类型分桶、按分数排序即可，所以生成很快。

这个设计很重要：

```text
日报是 Publisher，不是 Processor。
```

日报不应该承担抓取、摘要、分类、评分。日报只消费已经处理好的结构化数据。

因此我们的日报模块应该非常薄：

```text
DailyDigestBuilder(
  channel,
  date_window,
  categories,
  max_items_per_category
) -> DailyDigest
```

如果日报生成还需要大量 LLM 临场推理，说明前面的入库处理没有做深。

## 第二篇：AIHOT Skill / RSS / API 的分发模型

文章标题是“装了这个AI热点Skill之后，你再也不需要自己去刷AI新闻了。”，重点是把网站能力从 Web 页面扩展成机器可消费的数据能力。

### 1. 三种分发方式

AIHOT 开放了三种接入方式：

- Skill。
- RSS。
- REST API。

这不是三个附属功能，而是三个不同用户群体：

```text
Skill: Agent 用户。
RSS: 技术圈阅读器用户。
API: 公司内部系统或第三方产品集成。
```

这说明核心数据层必须和展示层分离。Web 页面只是一个消费端，Skill/RSS/API 也是消费端。

正确架构是：

```text
Processed Intelligence Store
  -> Web UI
  -> Skill endpoint
  -> RSS feeds
  -> REST API
  -> Daily digest
```

如果 Web 页面逻辑里塞满筛选、分类和日报生成，后续就无法自然开放 API、RSS 和 Skill。

### 2. Skill 的定位

文章里 Skill 的作用很明确：让 Agent 直接读取 AIHOT 的部分数据，嵌入到用户自己的工作流中。

它不是让 Agent 去浏览网页，也不是让 Agent 自己搜索新闻，而是给 Agent 一个稳定数据入口。

Skill 支持的能力包括：

- AI 日报。
- 精选模式。
- 按时间窗口查。
- 按分类查。
- 按关键词查。

默认策略是“保护注意力”：不明确要求全量时，默认走精选数据源。时间窗口最长 7 天，以控制数据量和服务负载。

这对我们很关键。Agent 接口不应该暴露无限自由检索，而应该提供几个受控查询模式：

```text
daily(channel, date)
selected(channel, window, category?)
all(channel, window, category?)
search(channel, keyword, window, mode)
event_cluster(event_id)
```

Agent 的自由度体现在“怎么问”和“怎么组织答案”，而不是绕开平台策略去随意拉全量数据。

### 3. Skill 输出格式

文章提到输出只做了基础 Markdown，因为 Skill 用户可以自行改格式。这背后是一个很实际的产品判断：

```text
平台提供干净数据和基本结构。
用户工作流决定最终呈现。
```

我们的 Skill 也应避免过度设计展示格式。核心是稳定 schema：

- 标题。
- 中文摘要。
- 分类。
- 来源。
- 原文链接。
- 时间。
- 分数。
- 入选理由。
- 建议动作。
- 相关事件簇。

Markdown 只是默认渲染，不是唯一输出。

### 4. RSS 的定位

RSS 是给不用 Agent 的用户。文章提到开放了三个 Feed：

- 精选动态。
- 全部 AI 动态。
- AI 日报。

这意味着 RSS 不是简单把所有数据塞进去，而是按消费场景拆 Feed。

我们的 RSS 也应该类似：

```text
/rss/ai/selected.xml
/rss/ai/all.xml
/rss/ai/daily.xml
/rss/amazon/selected.xml
/rss/amazon/all.xml
/rss/amazon/daily.xml
```

Amazon 频道还可以有更细分的风险类 Feed：

```text
/rss/amazon/policy.xml
/rss/amazon/account-health.xml
/rss/amazon/fba-fees.xml
```

### 5. API 的定位

API 面向公司内部系统和第三方产品集成。文章里提到 OpenAPI 文档由 Agent 辅助生成，但作者对 API 稳定性仍有顾虑。

对我们来说，这说明 API 不能后补。因为一旦外部系统接入，字段命名、分页、过滤、错误码、版本管理都会变成长期约束。

从第一版就应该有：

- 版本前缀：`/api/v1/...`
- 游标分页。
- 稳定 item schema。
- 错误码。
- OpenAPI 示例。
- 速率限制预留。

## 第三篇：脚本 / Skill / Agent 的运行哲学

文章标题是“能用脚本就别用Agent。”，这是整套系统的工程原则。

### 1. 三层金字塔

文章给出的优先级是：

```text
1. 能用脚本自动化解决的，用脚本。
2. 脚本搞不定但需要泛化能力的，做成 Skill。
3. 需要创造性判断和复杂推理的，交给 Agent。
```

这不是反 Agent，而是把 Agent 放在正确位置。

### 2. 循环关系

这三层不是静态分层，而是循环：

```text
Agent 发现流程
  -> 沉淀成 Skill
  -> 稳定后沉淀成脚本/服务
  -> 脚本执行高频任务
  -> Agent 继续处理未知问题
```

文章里最关键的句子可以概括为：

```text
让 Agent 去创造工具，让工具去执行任务。
```

对我们来说，情报系统里的 Agent 不应该每天亲自搜索、抓取、总结全部新闻。Agent 应该用于：

- 帮我们设计新信源策略。
- 分析评分策略是否失效。
- 对某个事件做深度解释。
- 给 Amazon 卖家推演行动方案。
- 生成周报、专题报告、机会判断。

而不应该用于：

- 定时抓取。
- URL 规范化。
- 去重。
- 公式打分。
- 阈值判断。
- API/RSS 输出。

## 图片和 UI 信息解读

### AIHOT 前台信息流

`site_01.jpg`、`site_02.png`、`site_06.png` 和 `skill_26.png` 显示了 AIHOT 的核心前台 UI：

- 左侧是固定导航。
- 主体是按时间线排列的信息卡片。
- 每条卡片包含来源、账号、标题、摘要、标签、分数、精选标识、推荐理由。
- 时间线按小时展示，说明产品强调“动态发生顺序”。
- 卡片底部有绿色推荐理由条，说明“为什么值得看”是显性产品信息。

左侧导航能看到：

- 精选。
- 全部 AI 动态。
- AI 日报。
- 低频爆文。
- 关于。
- 收藏。
- 信源。
- 信源提报。
- 精选策略。
- 策略反馈。
- 策略评估。

这暴露了一个重要事实：AIHOT 不只是前台信息流，它还有策略反馈、策略评估、信源管理等运营后台能力。真正的系统重点在“策略可运营”，不是只有用户端展示。

### 信源和信息漏斗

`site_05.png` 展示了信息管理面板，能看到抓取规模、信息统计和信源分布。它和正文中“168 个信源、某天 563 条抓取”的描述互相印证。

`site_07.png` 显示了信源管理式列表，说明信源并非写死在代码里，而是可被运营、分组、启停、分层管理。

`site_08.png` 是 OpenAI 官方 X 账号截图，用来说明官方社交账号属于重要但更杂的信源形态。结合正文里的 T1/T1.5/T2，能看出 AIHOT 的信源权重不是单一“官方/非官方”，而是区分官网、官方社交、KOL、媒体、综合站。

`site_09.png` 是漏斗图，表达从全量抓取到 AI 相关、再到精选的层层压缩。`site_10.png` 展示了被抓取但不一定值得精选的原始内容列表，例如 Apple 新闻中大量与 AI 无关的条目。

这一组图片强化了一个架构结论：系统必须保存“未精选、甚至未相关”的信息，因为这些数据用于衡量信源噪声、预筛效果和后续策略回测。

### 精选卡片和策略控制

`site_11.png` 展示了精选卡片上显式出现的分数和精选标记。它说明精选不是模糊推荐，而是有数值化判断。

`site_12.png` 展示了精选策略页面，包含策略指标、样本列表、阈值或策略相关数据。这说明 AIHOT 有策略运营后台，而不是只在代码里调整。

`site_13.png` 更像是策略/评分调试页，左侧是策略流或模块，右侧有类似结构化输出或日志的调试信息。它说明评分链路是可观察的。

`site_14.png` 展示了 AI 评分提示词或评分规则面板，和正文里“Prompt 从 600 行缩减到 200 行，模型只做五维评分”对应。

`site_15.png` 是很关键的一张图：它把评分拆成几个模块化环节，例如 AI 评分、计算基础分、精准判定，最后得到标题正文翻译或结构化结果。这张图直接证明了“LLM 输出中间量，代码策略做最终计算”的架构模式。

`site_16.png`、`site_17.png`、`site_18.jpg`、`site_19.png` 展示了策略反馈、策略评估、历史样本、策略变化或评分复盘类页面。这些图片说明 AIHOT 的评分系统不是一次性规则，而是一个可回测、可评估、可回滚、可持续迭代的策略系统。

### 事件聚类和日报

`site_20.png` 展示了同一事件下的多来源列表或折叠项，和正文中的 embedding 事件聚类完全对应。它不是简单去重，而是把同主题报道聚成事件簇。

`site_21.png` 展示了 AIHOT 日报页面。日报不是自由生成的大段文章，而是按模块、分类和条目排版的结构化输出。

这两张图确认了两个关键点：

- 前台默认应该展示事件，而不是裸 item。
- 日报是对已处理情报的发布层，不是重新抓取或重新推理。

### Agent 接入、Skill、RSS 和 API

`skill_25.jpg`、`skill_31.png`、`skill_32.png` 显示了 Agent 接入页：

- 页面标题是“把 AI HOT 接进你的工作流”。
- 三个 Tab：Skill、RSS、REST API。
- 文案强调匿名免费、无需 token。
- Skill 面向任意 Agent，遵循 `SKILL.md` 标准。

这个截图说明 AIHOT 把“数据分发”做成一等页面，而不是藏在文档里。对我们来说，后续也应该有一个专门的“接入中心”：

```text
Web 使用
Agent Skill
RSS
REST API
OpenAPI
示例请求
字段说明
```

`skill_33.png` 展示了 GitHub 上的 skill 仓库，说明 Skill 不只是网页说明，而是可被安装和分发的标准文件包。

`skill_34.png`、`skill_35.png` 展示了命令行 Agent 调用 AI 日报的结果，能看到 Skill 最终把结构化情报转成 Markdown 简报。

`skill_36.png`、`skill_37.png` 展示了精选或时间线查询结果。`skill_38.png`、`skill_39.png` 展示了按分类或时间窗口查询。`skill_40.png`、`skill_41.png` 展示了有 Skill 和无 Skill 时回答时效性的差异。

`skill_42.png` 展示 RSS Feed 页面，包含精选、全部动态、日报等 feed。`skill_43.png` 展示 REST API 文档页面，能看到接口列表和 OpenAPI 风格说明。

这些图片进一步证明：AIHOT 的真正产品结构是：

```text
用户端信息流
  + 策略运营后台
  + 信源管理后台
  + Agent/RSS/API 接入中心
```

它不是“一个页面 + 一个接口”的产品。

## 可抽象出的设计模式

### 1. 注意力漏斗模式

不是把所有内容都展示给用户，而是让信息逐层通过：

```text
可信信源
  -> 相关性
  -> 质量分
  -> 类别阈值
  -> 去重聚类
  -> 精选输出
```

### 2. 两级模型成本模式

便宜模型做粗筛，强模型做高价值判断：

```text
低成本模型：AI 相关性预筛。
高能力模型：五维评分、翻译、摘要。
代码公式：最终排序和精选判断。
```

### 3. LLM 中间量模式

LLM 不做最终控制决策，只输出可解释中间量。最终决策交给可回测、可调参、可版本化的代码策略。

### 4. 来源权威优先模式

同一事件中，官方源优先成为主条。KOL、媒体、社交账号可以提供补充，但不能覆盖一手来源。

### 5. 多出口同源模式

Web、RSS、API、Skill、日报都消费同一份处理后的情报资产。分发方式不同，核心数据不重复处理。

### 6. 策略运营模式

系统要有策略反馈、策略评估和信源提报能力。评分策略不是一次写死，而是长期运营的对象。

### 7. 工具沉淀模式

Agent 用来创造、调试和分析工具；成熟能力沉淀成脚本、服务或 Skill。

## 反推我们的目标架构

基于这三篇文章，我们现在的项目不能继续按“频道 YAML + 抓取脚本 + SQLite 入库”思路发展。那只是最小验证，不适合几百信源。

正式目标应该是：

```text
公开信源情报运行平台
```

而不是：

```text
新闻抓取脚本
```

### 1. 数据模型应升级

至少需要这些核心表或集合：

```text
sources
source_states
crawl_jobs
fetch_runs
raw_documents
normalized_items
screening_results
model_scores
ranked_items
event_clusters
cluster_members
daily_digests
publish_events
strategy_versions
feedback_events
```

关键点：

- `sources` 管信源定义。
- `source_states` 管运行状态。
- `crawl_jobs` 管调度。
- `raw_documents` 保存原始材料。
- `normalized_items` 保存规范化条目。
- `screening_results` 保存低成本预筛结果。
- `model_scores` 保存 LLM 中间评分。
- `ranked_items` 保存代码公式计算后的结果。
- `event_clusters` 解决重复报道。
- `strategy_versions` 让评分策略可回滚、可回测。

### 2. 模块边界应升级

建议的深模块：

```text
SourceRegistry
Scheduler
FetchWorker
FetchAdapter
RawStore
Extractor
Normalizer
PreScreener
LLMEnricher
RankPolicy
Clusterer
DigestBuilder
Publisher
FeedbackEvaluator
```

这些模块的职责要足够深：

- `SourceRegistry` 不只是读 YAML，而是管理信源生命周期。
- `Scheduler` 不只是循环所有源，而是根据频率、优先级、失败退避、预算生成任务。
- `FetchAdapter` 屏蔽 RSS、HTML、API、三方数据接口的差异。
- `RankPolicy` 集中所有权重、阈值和公式。
- `Clusterer` 专门处理同事件归并和主条选择。
- `Publisher` 专门输出 Web/RSS/API/Skill/日报。

### 3. 调度模型应升级

几百信源必须是任务队列模型：

```text
Scheduler 每分钟扫描到期信源
  -> 生成 crawl_jobs
  -> Worker 并发消费
  -> 每个 source 独立记录成功/失败/耗时/产出
  -> 失败自动 backoff
  -> 高价值源高频，低价值源低频
```

每个 source 至少要有：

- `enabled`
- `priority`
- `fetch_interval_minutes`
- `rate_limit`
- `timeout_seconds`
- `last_success_at`
- `last_error_at`
- `error_streak`
- `backoff_until`
- `health_score`
- `avg_latency_ms`
- `items_per_run`
- `duplicate_ratio`
- `noise_ratio`

### 4. 评分策略应升级

当前评分函数只能算 MVP。正式评分要分成两步：

```text
LLM semantic score:
  relevance
  novelty
  impact
  actionability
  credibility

Code rank policy:
  source tier
  source type
  category threshold
  entity hotness
  freshness
  duplicate penalty
  channel-specific impact
```

Amazon 频道还要加：

- marketplace 影响范围。
- seller risk level。
- fee impact。
- compliance urgency。
- operational actionability。
- affected seller type。

### 5. 聚类应成为核心能力

没有事件聚类，几百信源一定会重复污染精选流。聚类不是后期优化，而是第一版扩容架构的一部分。

聚类后的 item 应该变成：

```text
EventCluster
  - cluster_id
  - main_item_id
  - canonical_title
  - category
  - first_seen_at
  - last_seen_at
  - source_count
  - highest_authority_source
  - score
  - members[]
```

输出层默认展示 cluster，而不是裸 item。

### 6. 运营后台应预留

AIHOT 截图里暴露了策略反馈、策略评估、信源提报等功能。这说明长期系统必须有运营闭环。

我们至少要预留：

- 信源新增/暂停/降频。
- 信源健康看板。
- 精选误判反馈。
- 评分策略版本。
- 历史样本回测。
- 类别阈值调整。
- 事件聚类修正。

### 7. Agent 的位置

我们的 Agent 不应该替代平台流程。Agent 应该消费平台产出的结构化情报，并处理开放任务：

- “这件事对亚马逊美国站家居卖家有什么影响？”
- “最近 7 天 FBA 费用相关变化按紧急程度排序。”
- “复盘过去一个月 AI Agent 工具趋势。”
- “帮我发现评分策略最近是否漏掉了重要事件。”

确定性流程必须留在脚本和服务里。

## 对当前项目的直接修正

当前项目已经有方向雏形：

- 有频道配置。
- 有抓取器。
- 有规范化。
- 有 hash 去重。
- 有基础评分。
- 有 API。

但要按这三篇文章的真实架构深度推进，应调整优先级：

```text
不要先补日报/RSS/Skill。
先补 Source Registry、Scheduler、RawStore、RankPolicy、Clusterer 的架构骨架。
```

原因是：日报/RSS/Skill 是发布层，必须建立在稳定情报资产之上。否则会把薄 MVP 的数据直接分发出去，后续重构成本更高。

建议下一阶段路线：

1. 把 `channels/*.yaml` 从运行配置降级为 seed 配置。
2. 新增 `sources` 和 `source_states`。
3. 把 `crawl_enabled_sources` 改为 `Scheduler + JobRunner`。
4. 增加 `raw_documents`，保存抓取原文和 fetch metadata。
5. 把评分拆成 `ModelScore` 和 `RankPolicyScore`。
6. 设计 `event_clusters`，先用简单相似度占位，接口预留 embedding。
7. 再做日报、RSS、API、Skill。

## 一句话架构判断

AIHOT 的核心不是“用了 AI 抓热点”，而是：

```text
用确定性系统承载高频流程，
用 LLM 提供语义中间量，
用代码策略控制最终选择，
用多出口把同一份情报资产分发给人和 Agent。
```

这也应该成为我们项目的正式架构原则。
