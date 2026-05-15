export function channelLabel(value?: string | null) {
  return lookup(value, {
    ai: "AI 热点",
    amazon: "Amazon 情报"
  });
}

export function categoryLabel(value?: string | null) {
  return lookup(value, {
    ai_models: "AI 模型",
    ai_products: "AI 产品",
    agent_tools: "Agent 与工具",
    papers: "论文报告",
    monetization: "商业变现",
    ai_tools: "AI 工具",
    ai_agents: "AI Agent",
    ai_infra: "AI 基础设施",
    policy: "政策监管",
    account_health: "账号健康",
    fba_logistics: "FBA 物流",
    ads_ppc: "广告投放",
    listing_seo: "Listing 与搜索",
    fees_margin: "费用利润",
    tools: "卖家工具",
    compliance_trade: "合规贸易",
    funding: "融资并购",
    marketplace: "平台动态",
    ads: "广告投放",
    logistics: "物流履约",
    product_research: "选品研究",
    industry: "行业观察",
    seller_tools: "卖家工具"
  });
}

export function statusLabel(value?: string | null) {
  return lookup(value, {
    enabled: "启用",
    disabled: "停用",
    pending: "待处理",
    locked: "已领取",
    running: "运行中",
    succeeded: "成功",
    failed: "失败",
    cancelled: "已取消",
    dead: "死亡",
    draft: "草稿",
    active: "生效",
    retired: "已退役",
    completed: "已完成",
    approved: "已通过",
    rejected: "已拒绝",
    published: "已发布",
    unpublished: "未发布",
    usable: "可用",
    waiting: "等待抓取",
    backoff: "退避中",
    fetch_failed: "抓取失败",
    missing_publish_time: "缺少发布时间",
    invalid_original_url: "原文链接无效",
    no_current_items: "无最近 24 小时内容",
    no_accepted_items: "无有效条目",
    mostly_duplicates: "重复内容偏多",
    pending_api: "待接入",
    rate_limited: "限流",
    unavailable: "不可用",
    watch: "观察源",
    unread: "未处理",
    read: "已读",
    ignored: "已忽略"
  });
}

export function diagnosticStatusLabel(value?: string | null) {
  return lookup(value, {
    usable: "可用",
    waiting: "等待抓取",
    backoff: "退避中",
    fetch_failed: "抓取失败",
    missing_publish_time: "缺少发布时间",
    invalid_original_url: "原文链接无效",
    no_current_items: "无最近 24 小时内容",
    no_accepted_items: "无有效条目",
    mostly_duplicates: "重复内容偏多",
    disabled: "已停用",
    pending_api: "待接入",
    rate_limited: "限流",
    unavailable: "不可用"
  });
}

export function feedbackTypeLabel(value?: string | null) {
  return lookup(value, {
    false_positive: "误选",
    false_negative: "漏选",
    promote: "提权",
    demote: "降权",
    category_fix: "分类修正",
    general: "一般反馈"
  });
}

export function sourceTypeLabel(value?: string | null) {
  return lookup(value, {
    rss: "RSS",
    feed: "订阅源",
    html: "网页",
    api: "接口",
    manual: "人工",
    social: "社媒",
    forum: "社区",
    github: "GitHub",
    docs: "文档"
  });
}

export function sourceGroupLabel(value?: string | null) {
  return lookup(value, {
    official: "官方",
    first_party: "一手信源",
    media: "资讯",
    social: "推文",
    community: "社区",
    vendor: "服务商",
    curated: "精选聚合"
  });
}

export function collectionStatusLabel(value?: string | null) {
  return lookup(value, {
    collectable: "可抓取",
    pending_api: "待接入",
    rate_limited: "限流",
    unavailable: "不可用",
    watch: "观察源"
  });
}

export function fetchAdapterLabel(value?: string | null) {
  return lookup(value, {
    rss: "RSS 抓取",
    http_article: "网页抓取",
    html_list: "列表抓取",
    aihot_api: "AIHOT 接口",
    api: "接口抓取"
  });
}

export function modeLabel(value?: string | null) {
  return lookup(value, {
    selected: "精选",
    all: "全部"
  });
}

export function sellerActionLevelLabel(value?: string | null) {
  return lookup(value, {
    ignore: "仅关注",
    review: "建议查看",
    act: "建议行动",
    act_soon: "建议尽快行动",
    high: "建议尽快行动",
    urgent: "优先处理"
  });
}

export function roleLabel(value?: string | null) {
  return lookup(value, {
    guest: "游客",
    operator: "运营",
    admin: "管理员"
  });
}

export function permissionLabel(value?: string | null) {
  return lookup(value, {
    "public.read": "浏览公开内容",
    "feedback.create": "提交公开反馈",
    "ops.dashboard.read": "查看工作台",
    "sources.read": "查看信源",
    "sources.write": "新增/编辑信源",
    "health.read": "查看健康监控",
    "quality.read": "查看质量校准",
    "jobs.read": "查看任务队列",
    "jobs.retry": "重试任务",
    "events.read": "查看事件审核",
    "events.review": "审核事件",
    "daily.read": "查看日报发布",
    "daily.publish": "生成/发布日报",
    "strategies.read": "查看策略版本",
    "strategies.write": "创建/编辑策略",
    "strategies.activate": "激活策略",
    "feedback.read": "查看人工反馈",
    "feedback.update": "处理反馈",
    "evaluations.read": "查看评估运行",
    "evaluations.run": "执行评估",
    "users.manage": "管理用户",
    "roles.manage": "管理角色权限",
    "system.manage": "系统配置/审计"
  });
}

export function auditActionLabel(value?: string | null) {
  return lookup(value, {
    "sources.create": "新增信源",
    "sources.update": "更新信源",
    "jobs.retry": "重试任务",
    "strategies.create": "创建策略",
    "strategies.activate": "激活策略",
    "feedback.create": "新增反馈",
    "feedback.update": "处理反馈",
    "evaluations.create": "创建评估",
    "evaluations.run": "执行评估",
    "events.review": "审核事件",
    "daily.generate": "生成日报",
    "daily.publish": "发布日报",
    "daily.unpublish": "取消发布日报",
    "pipeline.run": "触发流水线",
    "users.create": "新增用户",
    "users.update": "更新用户",
    "roles.update": "更新角色权限"
  });
}

export function auditTargetTypeLabel(value?: string | null) {
  return lookup(value, {
    source: "信源",
    job: "任务",
    strategy: "策略",
    feedback: "反馈",
    feedback_event: "反馈",
    evaluation: "评估运行",
    evaluation_run: "评估运行",
    event: "事件",
    event_cluster: "事件",
    daily_digest: "日报",
    pipeline_run: "流水线",
    user: "用户",
    role: "角色"
  });
}

export function auditTargetLabel(type?: string | null, id?: string | number | null) {
  const label = auditTargetTypeLabel(type);
  return id ? `${label} ${id}` : label;
}

export function auditResultLabel(value?: string | null) {
  return lookup(value, {
    success: "成功",
    succeeded: "成功",
    failed: "失败",
    error: "失败",
    denied: "已拒绝",
    skipped: "已跳过"
  });
}

export function actorLabel(value?: string | null) {
  return lookup(value, {
    "public-user": "前台用户",
    guest: "游客",
    operator: "运营",
    admin: "管理员",
    system: "系统",
    worker: "系统任务"
  });
}

export function screenBucketLabel(value?: string | null) {
  return lookup(value, {
    core: "核心相关",
    related: "相关线索",
    watch: "观察线索",
    relevant: "相关",
    maybe: "待判断",
    irrelevant: "不相关",
    invalid: "无效内容"
  });
}

export function screenReasonCodeLabel(value?: string | null) {
  return lookup(value, {
    accepted: "已接收",
    test_provider: "测试数据",
    missing_publish_time: "缺少发布时间",
    invalid_original_url: "原文链接无效",
    channel_irrelevant: "频道相关度不足",
    duplicate_or_rewrite: "重复或改写内容",
    schema_invalid: "结构不合格",
    low_confidence: "低置信度",
    evergreen_tutorial: "常青教程",
    low_info_generic: "信息量不足",
    seller_ops_signal: "卖家运营信号",
    missing: "缺少关键信息"
  });
}

function lookup(value: string | null | undefined, labels: Record<string, string>) {
  if (!value) return "-";
  return labels[value] ?? value;
}
