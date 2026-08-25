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
  fetchIntervalMinutes?: number;
  enabled: boolean;
  visibility: string;
  sourceGroup?: string;
  publisherKey?: string | null;
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
  publisherKey?: string | null;
  socialHandle?: string | null;
  publishedAt?: string | null;
  summary?: string;
  imageUrl?: string | null;
  imageAlt?: string | null;
};

export type SupportedClaim = {
  claim: string;
  publisherKeys: string[];
  sourceIds: string[];
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
  verificationStatus?: "single_source" | "corroborated" | "conflicted" | "insufficient" | null;
  independentSourceCount?: number | null;
  authoritativeSourceCount?: number | null;
  evidenceScore?: number;
  evidenceSummary?: string | null;
  supportedFacts?: string[];
  supportedClaims?: SupportedClaim[];
  conflictingClaims?: string[];
  evidenceAnalyzedAt?: string | null;
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
  verificationStatus?: "single_source" | "corroborated" | "conflicted" | "insufficient" | null;
  independentSourceCount?: number | null;
  authoritativeSourceCount?: number | null;
  evidenceScore?: number;
  evidenceSummary?: string | null;
  supportedFacts?: string[];
  supportedClaims?: SupportedClaim[];
  conflictingClaims?: string[];
  evidenceAnalyzedAt?: string | null;
};

export type PublicEventDetail = {
  event: PublicEvent;
  members: EventMember[];
};

export type Page<T> = {
  items: T[];
  count: number;
  page?: number;
  pageSize?: number;
  total?: number;
  totalPages?: number;
  hasPrev?: boolean;
  hasNext: boolean;
  nextCursor: string | null;
  metrics?: Record<string, number>;
};

export type CurrentUser = {
  id: string | number | null;
  username: string;
  displayName: string;
};

export type UserPreferences = {
  theme: "dark" | "light" | "system";
  defaultChannel: "ai" | "amazon";
  compactMode: boolean;
};

export type SessionInfo = {
  user: CurrentUser | null;
  roles: string[];
  permissions: string[];
  preferences: UserPreferences;
  authenticated: boolean;
};

export type SystemSettings = {
  id: string;
  aiAnalysisEnabled: boolean;
  analysisMode: "ai" | "rules";
  provider: string;
  model: string;
  updatedBy: string | null;
  updatedAt: string | null;
};

export type UserAccount = {
  id: string;
  username: string;
  displayName: string;
  email?: string | null;
  status: string;
  roles: string[];
  preferences?: UserPreferences;
  lastLoginAt?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
};

export type Role = {
  id: string;
  name: string;
  description: string;
  locked: boolean;
  permissions: string[];
};

export type Permission = {
  id: string;
  name: string;
  description: string;
  group: string;
};

export type AuditLog = {
  id: string;
  actorUserId: string | null;
  actorUsername: string;
  action: string;
  targetType: string;
  targetId: string | null;
  result: string;
  metadata: Record<string, unknown>;
  createdAt: string | null;
};

export type DailyItem = {
  eventId?: string | null;
  title: string;
  summary?: string | null;
  entryReason?: string | null;
  category?: string | null;
  score?: number | null;
  sourceCount?: number | null;
  memberCount?: number | null;
  lastSeenAt?: string | null;
  mainItem?: MainItem | null;
};

export type DailySection = {
  category: string;
  label: string;
  count: number;
  items: DailyItem[];
};

export type DailyArchiveItem = {
  id: string;
  date: string;
  title: string;
  leadTitle?: string | null;
  storyCount?: number;
  generatedAt?: string | null;
};

export type PublicDaily = {
  id: string;
  channel: string;
  date: string;
  generatedAt: string | null;
  title: string;
  lead?: DailyItem | null;
  sections: DailySection[] | Record<string, unknown>;
  archiveItem?: DailyArchiveItem | null;
  stats?: { storyCount?: number; [key: string]: unknown };
  sectionsJson?: Record<string, unknown>;
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
  sections: DailySection[] | Record<string, unknown>;
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
  contact?: string | null;
  status?: string;
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
  channelMetrics?: Array<{
    channel: string;
    metrics: Dashboard["metrics"];
  }>;
  recentFailedJobs: Job[];
  pendingReviewEvents: EventCluster[];
  recentPipelineRuns: PipelineRun[];
};

export type QualityDashboard = {
  windowHours: number;
  generatedAt: string;
  channels: ChannelQuality[];
};

export type ChannelQuality = {
  channel: string;
  metrics: {
    sourceCount: number;
    enabledSourceCount: number;
    fetchRuns: number;
    successfulFetchRuns: number;
    rawDocuments: number;
    screenedItems: number;
    acceptedScreenings: number;
    rejectedScreenings: number;
    normalizedItems: number;
    scoredItems: number;
    rankedItems: number;
    selectedItems: number;
    eventClusters: number;
    approvedEvents: number;
    publicSelectedEvents: number;
  };
  conversion: {
    fetchSuccessRate: number;
    screenAcceptRate: number;
    selectedRate: number;
    approvedRate: number;
  };
  bottlenecks: string[];
  rejectionReasons: Array<{ reasonCode: string; bucket: string; reason: string; count: number }>;
  rejectionSamples: Array<{
    rawDocumentId: string;
    title: string;
    summary: string;
    sourceId: string;
    sourceName: string;
    sourceGroup: string;
    category: string;
    bucket: string;
    reasonCode: string;
    reason: string;
    confidenceScore: number;
    createdAt: string | null;
    url: string | null;
  }>;
  categoryBreakdown: Array<{ category: string; scoredItems: number; selectedItems: number; approvedEvents: number }>;
  sourceContributions: Array<{
    sourceId: string;
    sourceName: string;
    sourceGroup: string;
    collectionStatus: string;
    tier: string;
    healthScore: number;
    errorStreak: number;
    rawDocuments: number;
    acceptedScreenings: number;
    selectedItems: number;
  }>;
};
