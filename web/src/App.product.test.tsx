import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { PublicApi } from "./api";
import type { AdminApi } from "./api";
import { categoryLabel, channelLabel, feedbackTypeLabel, sourceTypeLabel, statusLabel } from "./labels";
import { DailyDigestsView } from "./views/DailyDigestsView";
import { DashboardView } from "./views/DashboardView";
import { EvaluationsView } from "./views/EvaluationsView";
import { EventsReviewView } from "./views/EventsReviewView";
import { PipelineRunsView } from "./views/PipelineRunsView";
import { PublicFrontPage } from "./views/PublicFrontPage";

function apiStub(overrides: Partial<AdminApi> = {}) {
  return {
    getDashboard: vi.fn().mockResolvedValue({
      metrics: {
        sourceCount: 7,
        healthWarningCount: 1,
        pendingJobCount: 2,
        failedJobCount: 1,
        pendingReviewEventCount: 3,
        publishedDailyCount: 4
      },
      recentFailedJobs: [],
      pendingReviewEvents: [],
      recentPipelineRuns: []
    }),
    listEvents: vi.fn().mockResolvedValue([
      {
        id: "1",
        channel: "ai",
        title: "OpenAI 发布 GPT-5",
        category: "ai_models",
        score: 91,
        sourceCount: 1,
        memberCount: 1,
        firstSeenAt: "2026-05-11T10:00:00Z",
        lastSeenAt: "2026-05-11T10:00:00Z",
        reviewStatus: "pending",
        reviewNote: null,
        reviewedBy: null,
        reviewedAt: null,
        mainItem: { title: "OpenAI 发布 GPT-5", sourceName: "OpenAI News", url: "https://example.com" }
      }
    ]),
    getEventDetail: vi.fn().mockResolvedValue({
      event: { id: "1", title: "OpenAI 发布 GPT-5" },
      members: [{ id: "1", title: "OpenAI 发布 GPT-5", sourceName: "OpenAI News", isMain: true }]
    }),
    reviewEvent: vi.fn().mockResolvedValue({ id: "1", reviewStatus: "approved" }),
    listDailyDigests: vi.fn().mockResolvedValue([]),
    generateDailyDigest: vi.fn().mockResolvedValue({
      dailyDigest: { id: "1", title: "AI 日报", published: true },
      eventCount: 1
    }),
    publishDailyDigest: vi.fn().mockResolvedValue({ id: "1", published: true }),
    unpublishDailyDigest: vi.fn().mockResolvedValue({ id: "1", published: false }),
    listPipelineRuns: vi.fn().mockResolvedValue([]),
    createPipelineRun: vi.fn().mockResolvedValue({ id: "1", status: "succeeded", succeeded: 0, failed: 0 }),
    listEvaluationRuns: vi.fn().mockResolvedValue([
      {
        id: "1",
        channel: "ai",
        strategyVersion: "ai-default-v1",
        name: "AI 评估",
        status: "succeeded",
        request: {},
        metrics: {
          labels: { selectedEventCount: "精选事件数", feedbackCount: "反馈总数" },
          values: { selectedEventCount: 2, feedbackCount: 1 }
        }
      }
    ]),
    createEvaluationRun: vi.fn(),
    runEvaluationRun: vi.fn(),
    ...overrides
  } as unknown as AdminApi;
}

describe("后台产品化界面", () => {
  it("shows a login page before rendering the workspace", async () => {
    sessionStorage.clear();
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (String(url).startsWith("/api/v1/internal/dashboard")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            metrics: { sourceCount: 7 },
            recentFailedJobs: [],
            pendingReviewEvents: [],
            recentPipelineRuns: []
          })
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({
          events: [
            {
              id: "1",
              channel: "ai",
              title: "OpenAI 发布 GPT-5",
              category: "ai_models",
              score: 91,
              sourceCount: 1,
              memberCount: 1,
              lastSeenAt: "2026-05-11T10:00:00Z",
              mainItem: { title: "OpenAI 发布 GPT-5", sourceName: "OpenAI News", summary: "OpenAI 发布新模型。" }
            }
          ]
        })
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByRole("heading", { name: "AI 热点" })).toBeInTheDocument();
    expect(screen.queryByText("信源管理")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "运营登录" }));
    fireEvent.change(screen.getByLabelText("管理员账号"), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText("管理员密码"), { target: { value: "admin" } });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));

    expect(await screen.findByRole("heading", { name: "工作台" })).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/internal/dashboard",
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Basic YWRtaW46YWRtaW4=" }) })
    );
  });

  it("uses public API without Basic Auth for the public front page", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ events: [], daily: null })
    });
    vi.stubGlobal("fetch", fetchMock);

    await new PublicApi().listEvents({ channel: "ai", mode: "selected", take: 10 });
    await new PublicApi().getDaily({ channel: "ai" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/public/events?channel=ai&mode=selected&take=10",
      expect.objectContaining({ headers: expect.not.objectContaining({ Authorization: expect.any(String) }) })
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/public/daily?channel=ai",
      expect.objectContaining({ headers: expect.not.objectContaining({ Authorization: expect.any(String) }) })
    );
  });

  it("separates public information architecture by AI and Amazon channel first", async () => {
    const publicApi = {
      listEvents: vi.fn().mockResolvedValue({ items: [], count: 0, hasNext: false, nextCursor: null }),
      listSources: vi.fn().mockResolvedValue([
        {
          id: "openai_social",
          channel: "ai",
          sourceType: "social",
          sourceGroup: "social",
          contributorNo: "AIHOT-001",
          socialHandle: "@OpenAI",
          collectionStatus: "pending_api",
          freeAccess: true,
          tier: "T1.5",
          name: "X: OpenAI",
          url: "https://x.com/OpenAI",
          language: "en",
          region: "global",
          authorityWeight: 92,
          noiseLevel: 0.12,
          fetchAdapter: "api",
          parserType: "x_timeline",
          defaultCategories: ["ai_products"],
          fetchIntervalMinutes: 60,
          enabled: false,
          visibility: "hidden"
        }
      ]),
      getEventDetail: vi.fn(),
      getDaily: vi.fn().mockResolvedValue(null)
    } as unknown as PublicApi;

    render(<PublicFrontPage api={publicApi} loginError={null} loginOpen={false} onLogin={vi.fn()} />);

    expect(screen.getByRole("navigation", { name: "频道分区" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "频道内功能" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AI 热点" })).toHaveClass("active");
    await userEvent.click(screen.getByRole("button", { name: "亚马逊情报" }));

    expect(screen.getByRole("button", { name: "亚马逊情报" })).toHaveClass("active");
    expect(screen.getByRole("button", { name: "精选" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "全部热点" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "日报" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "RSS 订阅" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "信源墙" })).toBeInTheDocument();
    await waitFor(() => expect(publicApi.listEvents).toHaveBeenCalledWith(expect.objectContaining({ channel: "amazon" })));
  });

  it("shows AIHOT-style source filters, contributor wall, and highlighted recommendation reason", async () => {
    const publicApi = {
      listEvents: vi.fn().mockResolvedValue({
        items: [
          {
            id: "1",
            channel: "ai",
            title: "OpenAI 发布新模型能力",
            summary: "OpenAI 发布模型能力更新，开发者需要关注 API 能力变化。",
            category: "ai_models",
            score: 86,
            sourceCount: 1,
            memberCount: 1,
            lastSeenAt: "2026-05-13T06:13:00Z",
            sourceGroup: "official",
            sourceType: "rss",
            sourceTier: "T1",
            entryReason: "推荐理由：来自官方一手信源，模型能力变化会影响开发者选型。",
            tags: ["OpenAI", "模型发布", "API 变化"],
            mainItem: { title: "OpenAI 发布新模型能力", sourceName: "OpenAI News", url: "https://openai.com/news/model" }
          }
        ],
        count: 1,
        hasNext: false,
        nextCursor: null
      }),
      listSources: vi.fn().mockResolvedValue([
        {
          id: "openai_social",
          channel: "ai",
          sourceType: "social",
          sourceGroup: "social",
          contributorNo: "AIHOT-001",
          socialHandle: "@OpenAI",
          collectionStatus: "pending_api",
          freeAccess: true,
          tier: "T1.5",
          name: "X: OpenAI",
          url: "https://x.com/OpenAI",
          language: "en",
          region: "global",
          authorityWeight: 92,
          noiseLevel: 0.12,
          fetchAdapter: "api",
          parserType: "x_timeline",
          defaultCategories: ["ai_products"],
          fetchIntervalMinutes: 60,
          enabled: false,
          visibility: "hidden"
        }
      ]),
      getEventDetail: vi.fn(),
      getDaily: vi.fn().mockResolvedValue(null)
    } as unknown as PublicApi;

    render(<PublicFrontPage api={publicApi} loginError={null} loginOpen={false} onLogin={vi.fn()} />);

    expect(await screen.findByText("OpenAI 发布新模型能力")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "一手信源" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "推文" })).toBeInTheDocument();
    expect(screen.getByText("推荐理由：来自官方一手信源，模型能力变化会影响开发者选型。")).toBeInTheDocument();
    expect(screen.getByText("精选分 86")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "信源墙" }));
    expect(await screen.findByText("X: OpenAI")).toBeInTheDocument();
    expect(screen.getByText("AIHOT · 001")).toBeInTheDocument();
    expect(screen.getByText("待接入")).toBeInTheDocument();
  }, 10000);

  it("maps platform values to Chinese labels", () => {
    expect(channelLabel("ai")).toBe("AI 热点");
    expect(channelLabel("amazon")).toBe("Amazon 情报");
    expect(categoryLabel("ai_models")).toBe("AI 模型");
    expect(categoryLabel("product_research")).toBe("选品研究");
    expect(feedbackTypeLabel("false_positive")).toBe("误选");
    expect(sourceTypeLabel("html")).toBe("网页");
    expect(statusLabel("approved")).toBe("已通过");
  });

  it("renders dashboard metrics", async () => {
    render(<DashboardView api={apiStub()} />);

    expect(await screen.findByText("信源总数")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getAllByText("待审核事件").length).toBeGreaterThan(0);
  });

  it("reviews an event from the event review page", async () => {
    const api = apiStub();
    render(<EventsReviewView api={api} />);

    expect(await screen.findByText("OpenAI 发布 GPT-5")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "通过" }));

    await waitFor(() => expect(api.reviewEvent).toHaveBeenCalledWith("1", expect.objectContaining({ reviewStatus: "approved" })));
  });

  it("generates a daily digest and triggers a pipeline run", async () => {
    const dailyApi = apiStub();
    render(<DailyDigestsView api={dailyApi} />);
    await userEvent.click(screen.getByRole("button", { name: "生成日报" }));
    await waitFor(() => expect(dailyApi.generateDailyDigest).toHaveBeenCalled());

    const pipelineApi = apiStub();
    render(<PipelineRunsView api={pipelineApi} />);
    await userEvent.click(screen.getByRole("button", { name: "触发流水线" }));
    await waitFor(() => expect(pipelineApi.createPipelineRun).toHaveBeenCalledWith({ workerId: "manual-worker", limit: 10 }));
  });

  it("shows evaluation metrics with Chinese labels", async () => {
    render(<EvaluationsView api={apiStub()} />);

    expect(await screen.findByText("精选事件数")).toBeInTheDocument();
    expect(screen.getByText("反馈总数")).toBeInTheDocument();
  });
});
