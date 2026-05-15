import type {
  DailyDigest,
  Dashboard,
  EvaluationRun,
  EventCluster,
  EventMember,
  FeedbackEvent,
  Job,
  PipelineRun,
  Page,
  QualityDashboard,
  PublicDaily,
  DailyArchiveItem,
  PublicEvent,
  PublicEventDetail,
  Source,
  SourceDiagnostic,
  SourceState,
  StrategyVersion
} from "./types";

export type Credentials = {
  username: string;
  password: string;
};

type QueryValue = string | number | boolean | null | undefined;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message);
  }
}

export function buildBasicAuthHeader(credentials: Credentials): string {
  return `Basic ${btoa(`${credentials.username}:${credentials.password}`)}`;
}

export class PublicApi {
  constructor(private baseUrl = "") {}

  async listEvents(
    filters: {
      channel?: string;
      mode?: "selected" | "all";
      category?: string;
      sourceGroup?: string;
      q?: string;
      date?: string;
      window?: number;
      take?: number;
      cursor?: string | null;
      page?: number;
      pageSize?: number;
    } = {}
  ): Promise<Page<PublicEvent>> {
    const response = await this.request<{
      count: number;
      page?: number;
      pageSize?: number;
      total?: number;
      totalPages?: number;
      hasPrev?: boolean;
      metrics?: Record<string, number>;
      events: PublicEvent[];
      hasNext: boolean;
      nextCursor: string | null;
    }>(`/api/v1/public/events${query(filters)}`);
    return {
      items: response.events,
      count: response.count,
      page: response.page,
      pageSize: response.pageSize,
      total: response.total,
      totalPages: response.totalPages,
      hasPrev: response.hasPrev,
      hasNext: response.hasNext,
      nextCursor: response.nextCursor,
      metrics: response.metrics
    };
  }

  async getEventDetail(eventId: string): Promise<PublicEventDetail> {
    return this.request<PublicEventDetail>(`/api/v1/public/events/${eventId}`);
  }

  async getDaily(filters: { channel: string; date?: string }): Promise<PublicDaily | null> {
    return (await this.request<{ daily: PublicDaily | null }>(`/api/v1/public/daily${query(filters)}`)).daily;
  }

  async listDailies(filters: { channel: string; page?: number; pageSize?: number }): Promise<Page<DailyArchiveItem>> {
    const response = await this.request<{
      items: DailyArchiveItem[];
      count: number;
      page?: number;
      pageSize?: number;
      total?: number;
      totalPages?: number;
      hasPrev?: boolean;
      metrics?: Record<string, number>;
      hasNext: boolean;
      nextCursor: string | null;
    }>(`/api/v1/public/dailies${query(filters)}`);
    return {
      items: response.items,
      count: response.count,
      page: response.page,
      pageSize: response.pageSize,
      total: response.total,
      totalPages: response.totalPages,
      hasPrev: response.hasPrev,
      hasNext: response.hasNext,
      nextCursor: response.nextCursor,
      metrics: response.metrics
    };
  }

  async listSources(filters: { channel?: string; sourceGroup?: string; page?: number; pageSize?: number } = {}): Promise<Source[]> {
    return (await this.listSourcesPage(filters)).items;
  }

  async listSourcesPage(filters: { channel?: string; sourceGroup?: string; page?: number; pageSize?: number } = {}): Promise<Page<Source>> {
    const response = await this.request<{
      sources: Source[];
      count: number;
      page?: number;
      pageSize?: number;
      total?: number;
      totalPages?: number;
      hasPrev?: boolean;
      metrics?: Record<string, number>;
      hasNext: boolean;
      nextCursor: string | null;
    }>(`/api/v1/public/sources${query(filters)}`);
    return {
      items: response.sources,
      count: response.count,
      page: response.page,
      pageSize: response.pageSize,
      total: response.total,
      totalPages: response.totalPages,
      hasPrev: response.hasPrev,
      hasNext: response.hasNext,
      nextCursor: response.nextCursor,
      metrics: response.metrics
    };
  }

  async submitFeedback(payload: {
    channel: string;
    feedbackType: string;
    reason: string;
    contact?: string | null;
    clusterId?: string | number | null;
    itemId?: string | number | null;
  }): Promise<FeedbackEvent> {
    return (await this.request<{ feedbackEvent: FeedbackEvent }>("/api/v1/public/feedback-events", {
      method: "POST",
      body: JSON.stringify(payload)
    })).feedbackEvent;
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: init.method,
      body: init.body,
      headers: {
        "Content-Type": "application/json",
        ...(init.headers ?? {})
      }
    });
    if (!response.ok) throw new ApiError(`请求失败：HTTP ${response.status}`, response.status);
    if (!responseContentType(response).includes("application/json")) {
      throw new ApiError("请求失败：情报接口没有返回 JSON 数据", response.status);
    }
    return response.json() as Promise<T>;
  }
}

export class AdminApi {
  constructor(
    private credentials: Credentials,
    private baseUrl = "",
    private onUnauthorized?: () => void
  ) {}

  async getDashboard(filters: { channel?: string } = {}): Promise<Dashboard> {
    return this.request<Dashboard>(`/api/v1/internal/dashboard${query(filters)}`);
  }

  async getQualityDashboard(filters: { window?: number } = {}): Promise<QualityDashboard> {
    return this.request<QualityDashboard>(`/api/v1/internal/quality-dashboard${query(filters)}`);
  }

  async listSources(channel?: string): Promise<Source[]> {
    return (await this.listSourcesPage({ channel, take: 200 })).items;
  }

  async listSourcesPage(
    filters: {
      channel?: string;
      q?: string;
      sourceGroup?: string;
      collectionStatus?: string;
      enabled?: boolean | string;
      take?: number;
      cursor?: string | null;
      page?: number;
      pageSize?: number;
    } = {}
  ): Promise<Page<Source>> {
    const response = await this.request<{
      count: number;
      page?: number;
      pageSize?: number;
      total?: number;
      totalPages?: number;
      hasPrev?: boolean;
      hasNext: boolean;
      nextCursor: string | null;
      metrics?: Record<string, number>;
      sources: Source[];
    }>(`/api/v1/internal/sources${query(filters)}`);
    return {
      items: response.sources,
      count: response.count,
      page: response.page,
      pageSize: response.pageSize,
      total: response.total,
      totalPages: response.totalPages,
      hasPrev: response.hasPrev,
      hasNext: response.hasNext,
      nextCursor: response.nextCursor,
      metrics: response.metrics
    };
  }

  async createSource(payload: Source): Promise<Source> {
    return (await this.request<{ source: Source }>("/api/v1/internal/sources", {
      method: "POST",
      body: JSON.stringify(payload)
    })).source;
  }

  async patchSource(sourceId: string, patch: Partial<Pick<Source, "enabled" | "visibility" | "notes">>): Promise<Source> {
    return (await this.request<{ source: Source }>(`/api/v1/internal/sources/${sourceId}`, {
      method: "PATCH",
      body: JSON.stringify(patch)
    })).source;
  }

  async listSourceStates(channel?: string): Promise<SourceState[]> {
    return (await this.request<{ sourceStates: SourceState[] }>(`/api/v1/internal/source-states${query({ channel })}`))
      .sourceStates;
  }

  async listSourceDiagnostics(channel?: string): Promise<SourceDiagnostic[]> {
    return (await this.listSourceDiagnosticsPage({ channel, take: 200 })).items;
  }

  async listSourceDiagnosticsPage(
    filters: {
      channel?: string;
      q?: string;
      sourceGroup?: string;
      collectionStatus?: string;
      freeAccess?: boolean | string;
      diagnosticStatus?: string;
      sort?: string;
      take?: number;
      cursor?: string | null;
      page?: number;
      pageSize?: number;
    } = {}
  ): Promise<Page<SourceDiagnostic>> {
    const response = await this.request<{
      count: number;
      page?: number;
      pageSize?: number;
      total?: number;
      totalPages?: number;
      hasPrev?: boolean;
      hasNext: boolean;
      nextCursor: string | null;
      metrics?: Record<string, number>;
      sourceDiagnostics: SourceDiagnostic[];
    }>(`/api/v1/internal/source-diagnostics${query(filters)}`);
    return {
      items: response.sourceDiagnostics,
      count: response.count,
      page: response.page,
      pageSize: response.pageSize,
      total: response.total,
      totalPages: response.totalPages,
      hasPrev: response.hasPrev,
      hasNext: response.hasNext,
      nextCursor: response.nextCursor,
      metrics: response.metrics
    };
  }

  async listJobs(filters: { channel?: string; status?: string } = {}): Promise<Job[]> {
    return (await this.request<{ jobs: Job[] }>(`/api/v1/internal/jobs${query(filters)}`)).jobs;
  }

  async retryJob(jobId: string): Promise<Job> {
    return (await this.request<{ job: Job }>(`/api/v1/internal/jobs/${jobId}/retry`, { method: "POST" })).job;
  }

  async listEvents(filters: { channel?: string; reviewStatus?: string; category?: string; q?: string } = {}): Promise<EventCluster[]> {
    return (await this.request<{ events: EventCluster[] }>(`/api/v1/internal/events${query(filters)}`)).events;
  }

  async getEventDetail(eventId: string): Promise<{ event: EventCluster; members: EventMember[] }> {
    return this.request<{ event: EventCluster; members: EventMember[] }>(`/api/v1/internal/events/${eventId}`);
  }

  async reviewEvent(
    eventId: string,
    payload: { reviewStatus: string; reviewNote?: string | null; actor?: string }
  ): Promise<EventCluster> {
    return (await this.request<{ event: EventCluster }>(`/api/v1/internal/events/${eventId}/review`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    })).event;
  }

  async listDailyDigests(filters: { channel?: string; date?: string } = {}): Promise<DailyDigest[]> {
    return (await this.request<{ dailyDigests: DailyDigest[] }>(`/api/v1/internal/daily-digests${query(filters)}`))
      .dailyDigests;
  }

  async generateDailyDigest(payload: {
    channel: string;
    date: string;
    strategyVersion: string;
  }): Promise<{ dailyDigest: DailyDigest; eventCount: number; created: boolean }> {
    return this.request<{ dailyDigest: DailyDigest; eventCount: number; created: boolean }>(
      "/api/v1/internal/daily-digests/generate",
      { method: "POST", body: JSON.stringify(payload) }
    );
  }

  async publishDailyDigest(digestId: string, actor = "operator"): Promise<DailyDigest> {
    return (await this.request<{ dailyDigest: DailyDigest }>(`/api/v1/internal/daily-digests/${digestId}/publish`, {
      method: "POST",
      body: JSON.stringify({ actor })
    })).dailyDigest;
  }

  async unpublishDailyDigest(digestId: string, actor = "operator"): Promise<DailyDigest> {
    return (await this.request<{ dailyDigest: DailyDigest }>(`/api/v1/internal/daily-digests/${digestId}/unpublish`, {
      method: "POST",
      body: JSON.stringify({ actor })
    })).dailyDigest;
  }

  async listStrategies(channel?: string): Promise<StrategyVersion[]> {
    return (await this.request<{ strategyVersions: StrategyVersion[] }>(
      `/api/v1/internal/strategy-versions${query({ channel })}`
    )).strategyVersions;
  }

  async createStrategy(payload: Record<string, unknown>): Promise<StrategyVersion> {
    return (await this.request<{ strategyVersion: StrategyVersion }>("/api/v1/internal/strategy-versions", {
      method: "POST",
      body: JSON.stringify(payload)
    })).strategyVersion;
  }

  async activateStrategy(strategyId: string): Promise<StrategyVersion> {
    return (await this.request<{ strategyVersion: StrategyVersion }>(
      `/api/v1/internal/strategy-versions/${strategyId}/activate`,
      { method: "POST" }
    )).strategyVersion;
  }

  async createFeedback(payload: FeedbackEvent): Promise<FeedbackEvent> {
    return (await this.request<{ feedbackEvent: FeedbackEvent }>("/api/v1/internal/feedback-events", {
      method: "POST",
      body: JSON.stringify(payload)
    })).feedbackEvent;
  }

  async listFeedbackEvents(filters: { channel?: string; feedbackType?: string; clusterId?: string } = {}): Promise<FeedbackEvent[]> {
    return (await this.request<{ feedbackEvents: FeedbackEvent[] }>(`/api/v1/internal/feedback-events${query(filters)}`))
      .feedbackEvents;
  }

  async updateFeedbackStatus(feedbackId: string, status: string): Promise<FeedbackEvent> {
    return (await this.request<{ feedbackEvent: FeedbackEvent }>(`/api/v1/internal/feedback-events/${feedbackId}`, {
      method: "PATCH",
      body: JSON.stringify({ status })
    })).feedbackEvent;
  }

  async createEvaluationRun(payload: Record<string, unknown>): Promise<EvaluationRun> {
    return (await this.request<{ evaluationRun: EvaluationRun }>("/api/v1/internal/evaluation-runs", {
      method: "POST",
      body: JSON.stringify(payload)
    })).evaluationRun;
  }

  async listEvaluationRuns(filters: { channel?: string } = {}): Promise<EvaluationRun[]> {
    return (await this.request<{ evaluationRuns: EvaluationRun[] }>(`/api/v1/internal/evaluation-runs${query(filters)}`))
      .evaluationRuns;
  }

  async runEvaluationRun(runId: string): Promise<EvaluationRun> {
    return (await this.request<{ evaluationRun: EvaluationRun }>(`/api/v1/internal/evaluation-runs/${runId}/run`, {
      method: "POST"
    })).evaluationRun;
  }

  async listPipelineRuns(): Promise<PipelineRun[]> {
    return (await this.request<{ pipelineRuns: PipelineRun[] }>("/api/v1/internal/pipeline-runs")).pipelineRuns;
  }

  async createPipelineRun(payload: { workerId: string; limit: number }): Promise<PipelineRun> {
    return (await this.request<{ pipelineRun: PipelineRun }>("/api/v1/internal/pipeline-runs", {
      method: "POST",
      body: JSON.stringify(payload)
    })).pipelineRun;
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: init.method,
      body: init.body,
      headers: {
        "Content-Type": "application/json",
        Authorization: buildBasicAuthHeader(this.credentials),
        ...(init.headers ?? {})
      }
    });
    if (!response.ok) {
      if (response.status === 401) this.onUnauthorized?.();
      throw new ApiError(`请求失败：HTTP ${response.status}`, response.status);
    }
    if (!responseContentType(response).includes("application/json")) {
      throw new ApiError("请求失败：后台接口没有返回 JSON 数据", response.status);
    }
    return response.json() as Promise<T>;
  }
}

function query(values: Record<string, QueryValue>) {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  });
  const text = params.toString();
  return text ? `?${text}` : "";
}

function responseContentType(response: Response) {
  return response.headers?.get?.("content-type") ?? "application/json";
}
