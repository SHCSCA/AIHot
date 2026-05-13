export type Source = {
  id: string;
  channel: string;
  sourceType: string;
  tier: string;
  name: string;
  url: string;
  language: string;
  region: string;
  authorityWeight: number;
  noiseLevel: number;
  fetchAdapter: string;
  parserType: string;
  defaultCategories: string[];
  fetchIntervalMinutes: number;
  enabled: boolean;
  visibility: string;
  sourceGroup?: string;
  contributorNo?: string | null;
  socialHandle?: string | null;
  collectionStatus?: string;
  freeAccess?: boolean;
  notes?: string | null;
};

export type SourceState = {
  sourceId: string;
  channel: string;
  sourceName: string;
  enabled: boolean;
  lastSuccessAt: string | null;
  lastErrorAt: string | null;
  errorStreak: number;
  nextFetchAt: string | null;
  backoffUntil: string | null;
  avgLatencyMs: number | null;
  itemsPerRun: number | null;
  healthScore: number;
  duplicateRatio: number;
  noiseRatio: number;
};

export type SourceDiagnostic = {
  sourceId: string;
  sourceName: string;
  channel: string;
  tier: string;
  enabled: boolean;
  sourceGroup?: string;
  collectionStatus?: string;
  freeAccess?: boolean;
  diagnosticStatus: string;
  diagnosticLabel: string;
  healthScore: number;
  errorStreak: number;
  duplicateRatio: number;
  noiseRatio: number;
  nextFetchAt: string | null;
  lastSuccessAt: string | null;
  lastErrorAt: string | null;
  backoffUntil: string | null;
  rawCount24h: number;
  lastRun: {
    id: string;
    status: string;
    startedAt: string | null;
    finishedAt: string | null;
    httpStatus: number | null;
    contentType: string | null;
    bytesReceived: number;
    itemCount: number;
    candidateItems: number;
    acceptedItems: number;
    skippedOldItems: number;
    skippedMissingDate: number;
    skippedInvalidOriginalUrl: number;
    errorMessage: string | null;
  } | null;
  lastJob: Job | null;
  screening: {
    latestStatus: string | null;
    latestBucket: string | null;
    latestReasonCode: string | null;
    latestReason: string | null;
    latestAt: string | null;
    accepted24h: number;
    rejected24h: number;
  };
};

export type Job = {
  id: string;
  sourceId: string;
  status: string;
  priority: number;
  runAfter: string | null;
  lockedAt: string | null;
  lockedBy: string | null;
  attemptCount: number;
  lastError: string | null;
  createdAt?: string;
  updatedAt?: string;
};

export type MainItem = {
  id?: string;
  title: string;
  url?: string;
  sourceId?: string;
  sourceName?: string;
  sourceGroup?: string | null;
  sourceType?: string | null;
  sourceTier?: string | null;
  socialHandle?: string | null;
  publishedAt?: string | null;
  summary?: string;
};

export type EventCluster = {
  id: string;
  channel: string;
  title: string;
  category: string;
  score: number;
  sourceCount: number;
  memberCount: number;
  firstSeenAt: string | null;
  lastSeenAt: string | null;
  mainItem: MainItem | null;
  reviewStatus?: string;
  reviewNote?: string | null;
  reviewedBy?: string | null;
  reviewedAt?: string | null;
  rank?: Record<string, unknown> | null;
  modelScore?: Record<string, unknown> | null;
  screenStatus?: string | null;
  screenBucket?: string | null;
  screenReasonCode?: string | null;
  screenReason?: string | null;
  riskFlags?: string[];
};

export type PublicEvent = {
  id: string;
  channel: string;
  title: string;
  summary?: string | null;
  category: string;
  score: number;
  sourceCount: number;
  memberCount: number;
  firstSeenAt: string | null;
  lastSeenAt: string | null;
  mainItem: MainItem | null;
  entryReason?: string | null;
  suggestedAction?: string | null;
  sellerActionLevel?: string | null;
  confidenceScore?: number | null;
  tags?: string[];
  eventType?: string | null;
  keyFacts?: string[];
  sourceGroup?: string | null;
  sourceType?: string | null;
  sourceTier?: string | null;
  socialHandle?: string | null;
  windowLabel?: string;
};

export type PublicEventDetail = {
  event: PublicEvent;
  members: EventMember[];
};

export type Page<T> = {
  items: T[];
  count: number;
  hasNext: boolean;
  nextCursor: string | null;
};

export type PublicDaily = {
  id: string;
  channel: string;
  date: string;
  generatedAt: string | null;
  title: string;
  sections: Record<string, unknown>;
  windowLabel?: string;
};

export type PublicFeedLink = {
  label: string;
  url: string;
  description: string;
};

export type EventMember = MainItem & {
  id: string;
  isMain: boolean;
  relationScore?: number;
  rank?: Record<string, unknown> | null;
  modelScore?: Record<string, unknown> | null;
};

export type DailyDigest = {
  id: string;
  channel: string;
  date: string;
  generatedAt: string | null;
  strategyVersion: string;
  title: string;
  sections: Record<string, unknown>;
  published: boolean;
  publishedBy: string | null;
  publishedAt: string | null;
};

export type PipelineRun = {
  id: string;
  workerId: string;
  limit: number;
  status: string;
  scheduled: number;
  claimed: number;
  succeeded: number;
  failed: number;
  rawDocumentsInserted: number;
  normalizedItems: number;
  rankedItems: number;
  clusters: number;
  errorMessage: string | null;
  startedAt: string | null;
  finishedAt: string | null;
};

export type StrategyVersion = {
  id: string;
  channel: string;
  name: string;
  status: string;
  thresholds: Record<string, unknown>;
  modelConfig: Record<string, unknown>;
};

export type FeedbackEvent = {
  id?: string;
  itemId?: string | null;
  clusterId?: string | null;
  channel: string;
  feedbackType: string;
  reason: string;
  actor: string;
  createdAt?: string | null;
};

export type EvaluationMetrics = {
  labels?: Record<string, string>;
  values?: Record<string, unknown>;
};

export type EvaluationRun = {
  id: string;
  channel: string;
  strategyVersion: string;
  name: string;
  status: string;
  request: Record<string, unknown>;
  metrics: EvaluationMetrics;
  createdAt?: string | null;
  completedAt?: string | null;
};

export type Dashboard = {
  metrics: {
    sourceCount?: number;
    healthWarningCount?: number;
    pendingJobCount?: number;
    failedJobCount?: number;
    pendingReviewEventCount?: number;
    publishedDailyCount?: number;
  };
  recentFailedJobs: Job[];
  pendingReviewEvents: EventCluster[];
  recentPipelineRuns: PipelineRun[];
};
