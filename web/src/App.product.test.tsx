import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { PublicApi } from "./api";
import type { AdminApi } from "./api";
import {
  categoryLabel,
  channelLabel,
  feedbackTypeLabel,
  sellerActionLevelLabel,
  sourceTypeLabel,
  statusLabel
} from "./labels";
import { DailyDigestsView } from "./views/DailyDigestsView";
import { DashboardView } from "./views/DashboardView";
import { EvaluationsView } from "./views/EvaluationsView";
import { EventsReviewView } from "./views/EventsReviewView";
import { FeedbackView } from "./views/FeedbackView";
import { HealthView } from "./views/HealthView";
import { PipelineRunsView } from "./views/PipelineRunsView";
import { PublicFrontPage } from "./views/PublicFrontPage";
import { QualityView } from "./views/QualityView";
import { SourcesView } from "./views/SourcesView";

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
      recentPipelineRuns: [],
      channelMetrics: [
        { channel: "ai", metrics: { sourceCount: 7, healthWarningCount: 1, pendingJobCount: 2, failedJobCount: 1, pendingReviewEventCount: 3, publishedDailyCount: 4 } },
        { channel: "amazon", metrics: { sourceCount: 5, healthWarningCount: 0, pendingJobCount: 1, failedJobCount: 0, pendingReviewEventCount: 1, publishedDailyCount: 2 } }
      ]
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
    getQualityDashboard: vi.fn().mockResolvedValue({
      windowHours: 24,
      generatedAt: "2026-05-13T09:00:00Z",
      channels: [
        {
          channel: "ai",
          metrics: {
            sourceCount: 26,
            enabledSourceCount: 19,
            fetchRuns: 175,
            successfulFetchRuns: 163,
            rawDocuments: 58,
            screenedItems: 39,
            acceptedScreenings: 11,
            rejectedScreenings: 26,
            normalizedItems: 11,
            scoredItems: 11,
            rankedItems: 11,
            selectedItems: 0,
            eventClusters: 10,
            approvedEvents: 3,
            publicSelectedEvents: 0
          },
          conversion: { fetchSuccessRate: 0.93, screenAcceptRate: 0.28, selectedRate: 0, approvedRate: 0.3 },
          bottlenecks: ["已有 AI 初筛通过项，但没有精选，优先校准精筛分数、置信度和精选阈值。"],
          rejectionReasons: [{ reasonCode: "low_confidence", bucket: "invalid", reason: "置信度不足", count: 8 }],
          rejectionSamples: [
            {
              rawDocumentId: "101",
              title: "旧教程内容",
              summary: "这是一条没有新增事实的旧教程。",
              sourceId: "simon_willison_blog",
              sourceName: "Simon Willison Blog",
              sourceGroup: "media",
              category: "ai_models",
              bucket: "invalid",
              reasonCode: "low_confidence",
              reason: "置信度不足",
              confidenceScore: 42,
              createdAt: "2026-05-13T08:00:00Z",
              url: "https://example.com/old"
            }
          ],
          categoryBreakdown: [{ category: "ai_models", scoredItems: 11, selectedItems: 0, approvedEvents: 3 }],
          sourceContributions: [
            {
              sourceId: "simon_willison_blog",
              sourceName: "Simon Willison Blog",
              sourceGroup: "first_party",
              collectionStatus: "collectable",
              tier: "T2",
              healthScore: 100,
              errorStreak: 0,
              rawDocuments: 8,
              acceptedScreenings: 3,
              selectedItems: 0
            }
          ]
        }
      ]
    }),
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
    listFeedbackEvents: vi.fn().mockResolvedValue([]),
    createFeedback: vi.fn(),
    ...overrides
  } as unknown as AdminApi;
}

describe("后台产品化界面", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("shows a login page before rendering the workspace", async () => {
    sessionStorage.clear();
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (String(url).startsWith("/api/v1/me")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            user: null,
            roles: ["guest"],
            permissions: ["feedback.create", "public.read"],
            preferences: { theme: "dark", defaultChannel: "ai", compactMode: false },
            authenticated: false
          })
        });
      }
      if (String(url).startsWith("/api/v1/auth/login")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            user: { id: "1", username: "admin", displayName: "系统管理员" },
            roles: ["admin"],
            permissions: [
              "public.read",
              "feedback.create",
              "ops.dashboard.read",
              "sources.read",
              "health.read",
              "quality.read",
              "jobs.read",
              "events.read",
              "daily.read",
              "strategies.read",
              "feedback.read",
              "evaluations.read",
              "users.manage",
              "roles.manage",
              "system.manage"
            ],
            preferences: { theme: "dark", defaultChannel: "ai", compactMode: false },
            authenticated: true
          })
        });
      }
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

    expect(await screen.findByRole("heading", { name: "精选" })).toBeInTheDocument();
    expect(screen.queryByText("信源管理")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "运营登录" }));
    expect(await screen.findByRole("heading", { name: "AIHOT 运营入口" })).toBeInTheDocument();
    expect(screen.getByText("普通访客无需登录即可继续浏览公开内容。")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("管理员账号"), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText("管理员密码"), { target: { value: "admin" } });
    fireEvent.click(screen.getByRole("button", { name: /进入运营工作台/ }));

    expect(await screen.findByRole("button", { name: /信源管理/ })).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: /工作台/ })[0]);
    expect(await screen.findByRole("heading", { name: "工作台" })).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/internal/dashboard?channel=ai",
      expect.objectContaining({
        credentials: "include",
        headers: expect.not.objectContaining({ Authorization: expect.any(String) })
      })
    );
  });

  it("shows a friendly 401 message on admin login failure", async () => {
    window.history.replaceState(null, "", "/admin/dashboard");
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (String(url).startsWith("/api/v1/me")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            user: null,
            roles: ["guest"],
            permissions: ["feedback.create", "public.read"],
            preferences: { theme: "dark", defaultChannel: "ai", compactMode: false },
            authenticated: false
          })
        });
      }
      if (String(url).startsWith("/api/v1/auth/login")) {
        return Promise.resolve({
          ok: false,
          status: 401,
          headers: { get: () => "application/json" },
          json: async () => ({ detail: "invalid username or password" })
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({ events: [] }) });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByRole("heading", { name: "AIHOT 运营入口" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("管理员账号"), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText("管理员密码"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /进入运营工作台/ }));

    expect(await screen.findByText("账号或密码不正确，请检查后台账号后再试。")).toBeInTheDocument();
  });

  it("keeps the local theme preference for guest sessions", async () => {
    localStorage.setItem("publicTheme", "light");
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (String(url).startsWith("/api/v1/me")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            user: null,
            roles: ["guest"],
            permissions: ["feedback.create", "public.read"],
            preferences: { theme: "system", defaultChannel: "ai", compactMode: false },
            authenticated: false
          })
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ events: [] })
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByRole("heading", { name: "精选" })).toBeInTheDocument();
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("light"));
    expect(localStorage.getItem("publicTheme")).toBe("light");
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
      getDaily: vi.fn().mockResolvedValue(null),
      submitFeedback: vi.fn().mockResolvedValue({ id: "1" })
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
    expect(screen.getByRole("button", { name: "反馈" })).toBeInTheDocument();
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
      getDaily: vi.fn().mockResolvedValue(null),
      submitFeedback: vi.fn().mockResolvedValue({ id: "1" })
    } as unknown as PublicApi;

    render(<PublicFrontPage api={publicApi} loginError={null} loginOpen={false} onLogin={vi.fn()} />);

    expect(await screen.findByText("OpenAI 发布新模型能力")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "官方/一手" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "社媒/社区" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "服务商" })).not.toBeInTheDocument();
    expect(screen.getByText("推荐理由：来自官方一手信源，模型能力变化会影响开发者选型。")).toBeInTheDocument();
    expect(screen.getByText("精选分 86")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "信源墙" }));
    expect(await screen.findByText("X: OpenAI")).toBeInTheDocument();
    expect(screen.getByText("AIHOT · 001")).toBeInTheDocument();
    expect(screen.getByText("待接入")).toBeInTheDocument();
  }, 10000);

  it("renders event cards with thumbnails and numbered pagination", async () => {
    const publicApi = {
      listEvents: vi
        .fn()
        .mockResolvedValueOnce({
          items: [
            {
              id: "1",
              channel: "ai",
              title: "Claude 工具更新",
              summary: "Claude 发布面向开发者的工具更新。",
              category: "agent_tools",
              score: 82,
              sourceCount: 1,
              memberCount: 1,
              lastSeenAt: "2026-05-14T06:13:00Z",
              entryReason: "推荐理由：该更新会影响开发者工作流。",
              tags: ["Claude", "工具更新"],
              mainItem: {
                title: "Claude 工具更新",
                sourceName: "Anthropic News",
                url: "https://anthropic.com/news/tool",
                imageUrl: "https://anthropic.com/tool.png",
                imageAlt: "Claude 工具截图"
              }
            }
          ],
          count: 1,
          page: 1,
          pageSize: 20,
          total: 31,
          totalPages: 2,
          hasPrev: false,
          hasNext: true,
          nextCursor: null
        })
        .mockResolvedValueOnce({
          items: [],
          count: 0,
          page: 2,
          pageSize: 20,
          total: 31,
          totalPages: 2,
          hasPrev: true,
          hasNext: false,
          nextCursor: null
        }),
      listSources: vi.fn().mockResolvedValue([]),
      getEventDetail: vi.fn(),
      getDaily: vi.fn().mockResolvedValue(null),
      listDailies: vi.fn().mockResolvedValue({ items: [], count: 0, page: 1, pageSize: 20, total: 0, totalPages: 1 }),
      submitFeedback: vi.fn().mockResolvedValue({ id: "1" })
    } as unknown as PublicApi;

    render(<PublicFrontPage api={publicApi} loginError={null} loginOpen={false} onLogin={vi.fn()} />);

    expect(await screen.findByText("Claude 工具更新")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Claude 工具截图" })).toHaveAttribute("src", "https://anthropic.com/tool.png");
    expect(screen.getByRole("img", { name: "Claude 工具截图" }).closest("figure")).toHaveClass("event-media-natural");
    await userEvent.click(screen.getAllByRole("button", { name: "下一页" })[0]);

    await waitFor(() => expect(publicApi.listEvents).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, pageSize: 20 })));
  });

  it("renders magazine style daily reader with archive and section document", async () => {
    const publicApi = {
      listEvents: vi.fn().mockResolvedValue({ items: [], count: 0, page: 1, pageSize: 20, total: 0, totalPages: 1, hasNext: false, nextCursor: null }),
      listSources: vi.fn().mockResolvedValue([]),
      getEventDetail: vi.fn(),
      getDaily: vi.fn().mockResolvedValue({
        id: "daily-1",
        channel: "ai",
        date: "2026-05-14",
        generatedAt: "2026-05-14T08:00:00+08:00",
        title: "AIHOT 日报",
        windowLabel: "基于最近 24 小时精选情报自动生成",
        stats: { storyCount: 2 },
        sections: [
          {
            category: "ai_models",
            label: "模型发布/更新",
            count: 1,
            items: [
              {
                eventId: "1",
                title: "Hy3 预览版登陆 GMI",
                summary: "Hy3 预览版开放使用，模型能力持续增强。",
                category: "ai_models",
                score: 88,
                entryReason: "模型发布来自官方信源，值得关注。",
                mainItem: { title: "Hy3 预览版登陆 GMI", url: "https://example.com/hy3" }
              }
            ]
          },
          {
            category: "ai_products",
            label: "产品发布/更新",
            count: 1,
            items: [
              {
                eventId: "2",
                title: "Runway Agent 发布",
                summary: "Runway 发布视频创作 Agent。",
                category: "ai_products",
                score: 82
              }
            ]
          }
        ]
      }),
      listDailies: vi.fn().mockResolvedValue({
        items: [{ id: "daily-1", date: "2026-05-14", title: "AIHOT 日报", leadTitle: "Hy3 预览版登陆 GMI", storyCount: 2 }],
        count: 1,
        page: 1,
        pageSize: 20,
        total: 1,
        totalPages: 1,
        hasNext: false,
        nextCursor: null
      }),
      submitFeedback: vi.fn().mockResolvedValue({ id: "1" })
    } as unknown as PublicApi;

    render(<PublicFrontPage api={publicApi} loginError={null} loginOpen={false} onLogin={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "日报" }));

    expect(await screen.findByText("VOL.2026.05.14 · 2 STORIES · AI 热点 DAILY")).toBeInTheDocument();
    expect(screen.getByText("最新一期")).toBeInTheDocument();
    expect(screen.getByText("模型发布/更新")).toBeInTheDocument();
    expect(screen.getByText("产品发布/更新")).toBeInTheDocument();
    expect(screen.getByText("目录")).toBeInTheDocument();
    expect(screen.getAllByText("Hy3 预览版登陆 GMI").length).toBeGreaterThan(0);
  });

  it("switches between dark and light public themes", async () => {
    const publicApi = {
      listEvents: vi.fn().mockResolvedValue({ items: [], count: 0, page: 1, pageSize: 20, total: 0, totalPages: 1, hasNext: false, nextCursor: null }),
      listSources: vi.fn().mockResolvedValue([]),
      getEventDetail: vi.fn(),
      getDaily: vi.fn().mockResolvedValue(null),
      listDailies: vi.fn().mockResolvedValue({ items: [], count: 0, page: 1, pageSize: 20, total: 0, totalPages: 1 }),
      submitFeedback: vi.fn().mockResolvedValue({ id: "1" })
    } as unknown as PublicApi;

    render(<PublicFrontPage api={publicApi} loginError={null} loginOpen={false} onLogin={vi.fn()} />);

    expect(document.documentElement.dataset.theme).toBe("dark");
    await userEvent.click(screen.getByRole("button", { name: "浅色模式" }));
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("submits public user feedback as a quality signal", async () => {
    const publicApi = {
      listEvents: vi.fn().mockResolvedValue({ items: [], count: 0, hasNext: false, nextCursor: null }),
      listSources: vi.fn().mockResolvedValue([]),
      getEventDetail: vi.fn(),
      getDaily: vi.fn().mockResolvedValue(null),
      submitFeedback: vi.fn().mockResolvedValue({ id: "1" })
    } as unknown as PublicApi;

    render(<PublicFrontPage api={publicApi} loginError={null} loginOpen={false} onLogin={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "反馈" }));
    fireEvent.change(screen.getByLabelText("想说点什么？"), { target: { value: "这条内容不够相关" } });
    fireEvent.change(screen.getByLabelText("联系方式（选填）"), { target: { value: "wechat: demo" } });
    await userEvent.click(screen.getByRole("button", { name: "发送反馈" }));

    await waitFor(() =>
      expect(publicApi.submitFeedback).toHaveBeenCalledWith({
        channel: "ai",
        feedbackType: "general",
        contact: "wechat: demo",
        reason: "这条内容不够相关"
      })
    );
    expect(await screen.findByText("反馈已提交，后台会把它作为质量评估样本。")).toBeInTheDocument();
  });

  it("maps platform values to Chinese labels", () => {
    expect(channelLabel("ai")).toBe("AI 热点");
    expect(channelLabel("amazon")).toBe("Amazon 情报");
    expect(categoryLabel("ai_models")).toBe("AI 模型");
    expect(categoryLabel("product_research")).toBe("选品研究");
    expect(feedbackTypeLabel("false_positive")).toBe("误选");
    expect(sourceTypeLabel("html")).toBe("网页");
    expect(statusLabel("approved")).toBe("已通过");
    expect(sellerActionLevelLabel("act_soon")).toBe("建议尽快行动");
  });

  it("renders dashboard metrics", async () => {
    render(<DashboardView api={apiStub()} />);

    expect(await screen.findByText("信源总数")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getAllByText("待审核事件").length).toBeGreaterThan(0);
  });

  it("keeps event review as AI review monitoring rather than manual approval", async () => {
    const api = apiStub();
    render(<EventsReviewView api={api} />);

    expect(await screen.findByText("OpenAI 发布 GPT-5")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "通过" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "拒绝" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "提交反馈" })).not.toBeInTheDocument();
  });

  it("shows daily digests as auto-published monitoring without manual publish controls", async () => {
    const dailyApi = apiStub();
    render(<DailyDigestsView api={dailyApi} />);

    expect(await screen.findByText("日报发布")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "生成日报" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "发布" })).not.toBeInTheDocument();
  });

  it("triggers a pipeline run from the pipeline console", async () => {
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

  it("shows quality calibration funnel and bottlenecks", async () => {
    render(<QualityView api={apiStub()} />);

    expect(await screen.findByText("AI 热点质量漏斗")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /AI 热点/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "拒绝样本" })).toBeInTheDocument();
    const funnel = screen.getByLabelText("AI 热点漏斗");
    expect(within(funnel).getByText("原始条目")).toBeInTheDocument();
    expect(within(funnel).getByText("58")).toBeInTheDocument();
    expect(screen.getByText("已有 AI 初筛通过项，但没有精选，优先校准精筛分数、置信度和精选阈值。")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "拒绝样本" }));
    expect(await screen.findByText("旧教程内容")).toBeInTheDocument();
    expect(screen.getByText("这是一条没有新增事实的旧教程。")).toBeInTheDocument();
    expect(screen.getByText("置信度不足")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "信源贡献" }));
    expect(screen.getByText("Simon Willison Blog")).toBeInTheDocument();
  });

  it("does not expose manual feedback creation in the admin feedback page", async () => {
    render(<FeedbackView api={apiStub()} />);

    expect(await screen.findByText("反馈历史")).toBeInTheDocument();
    expect(screen.queryByText("提交人工反馈")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "提交反馈" })).not.toBeInTheDocument();
  });

  it("loads source pages in the admin source view", async () => {
    const api = apiStub({
      listSourcesPage: vi.fn().mockImplementation(({ page = 1, pageSize = 50 }) => {
        if (pageSize === 6) {
          return Promise.resolve({
            items: [{ id: "wall_a", name: "Wall Source", channel: "ai", sourceType: "rss", sourceGroup: "media", collectionStatus: "collectable", tier: "T2", fetchAdapter: "rss", fetchIntervalMinutes: 60, visibility: "public", enabled: true, authorityWeight: 80, noiseLevel: 0.1, parserType: "rss", defaultCategories: [], language: "en", region: "global", url: "https://example.com/wall.xml", freeAccess: true }],
            count: 1,
            page,
            pageSize,
            total: 7,
            totalPages: 2,
            hasNext: true,
            nextCursor: null,
            metrics: { sourceCount: 203, enabledSourceCount: 180, highAuthorityCount: 18, pendingSocialCount: 9 }
          });
        }
        if (page === 2) {
          return Promise.resolve({
            items: [{ id: "source_b", name: "Source B", channel: "ai", sourceType: "rss", sourceGroup: "media", collectionStatus: "collectable", tier: "T2", fetchAdapter: "rss", fetchIntervalMinutes: 60, visibility: "public", enabled: true, authorityWeight: 80, noiseLevel: 0.1, parserType: "rss", defaultCategories: [], language: "en", region: "global", url: "https://example.com/b.xml", freeAccess: true }],
            count: 1,
            page,
            pageSize,
            total: 203,
            totalPages: 41,
            hasNext: true,
            nextCursor: null,
            metrics: { sourceCount: 203, enabledSourceCount: 180, highAuthorityCount: 18, pendingSocialCount: 9 }
          });
        }
        return Promise.resolve({
          items: [{ id: "source_a", name: "Source A", channel: "ai", sourceType: "rss", sourceGroup: "media", collectionStatus: "collectable", tier: "T2", fetchAdapter: "rss", fetchIntervalMinutes: 60, visibility: "public", enabled: true, authorityWeight: 80, noiseLevel: 0.1, parserType: "rss", defaultCategories: [], language: "en", region: "global", url: "https://example.com/a.xml", freeAccess: true }],
          count: 1,
          page,
          pageSize,
          total: 203,
          totalPages: 41,
          hasNext: true,
          nextCursor: null,
          metrics: { sourceCount: 203, enabledSourceCount: 180, highAuthorityCount: 18, pendingSocialCount: 9 }
        });
      })
    });

    render(<SourcesView api={api} />);

    expect(await screen.findByText("Source A")).toBeInTheDocument();
    expect(screen.getByText("203")).toBeInTheDocument();
    expect(screen.getByText("Wall Source")).toBeInTheDocument();
    expect(api.listSourcesPage).toHaveBeenCalledWith(expect.objectContaining({ channel: "ai", pageSize: 50 }));
    expect(api.listSourcesPage).toHaveBeenCalledWith(expect.objectContaining({ channel: "ai", pageSize: 6 }));
    await userEvent.click(screen.getAllByRole("button", { name: "下一页" })[0]);
    expect(await screen.findByText("Source B")).toBeInTheDocument();
  });

  it("loads source diagnostic pages in the health view", async () => {
    const api = apiStub({
      listSourceDiagnosticsPage: vi.fn().mockImplementation(({ page = 1, pageSize = 50 }) => {
        if (page === 2) {
          return Promise.resolve({
            items: [{ sourceId: "source_b", sourceName: "Source B", channel: "ai", tier: "T2", enabled: true, diagnosticStatus: "usable", diagnosticLabel: "可用", healthScore: 90, errorStreak: 0, duplicateRatio: 0, noiseRatio: 0, nextFetchAt: null, lastSuccessAt: null, lastErrorAt: null, backoffUntil: null, rawCount24h: 0, lastRun: null, lastJob: null, screening: { accepted24h: 0, rejected24h: 0, latestStatus: null, latestBucket: null, latestReasonCode: null, latestReason: null, latestAt: null } }],
            count: 1,
            page,
            pageSize,
            total: 12,
            totalPages: 3,
            hasNext: true,
            nextCursor: null,
            metrics: { sourceCount: 12, averageHealthScore: 87, usableCount: 9, warningCount: 3, missingDateCount: 1, waitingCount: 2 }
          });
        }
        return Promise.resolve({
          items: [{ sourceId: "source_a", sourceName: "Source A", channel: "ai", tier: "T2", enabled: true, diagnosticStatus: "usable", diagnosticLabel: "可用", healthScore: 90, errorStreak: 0, duplicateRatio: 0, noiseRatio: 0, nextFetchAt: null, lastSuccessAt: null, lastErrorAt: null, backoffUntil: null, rawCount24h: 0, lastRun: null, lastJob: null, screening: { accepted24h: 0, rejected24h: 0, latestStatus: null, latestBucket: null, latestReasonCode: null, latestReason: null, latestAt: null } }],
          count: 1,
          page,
          pageSize,
          total: 12,
          totalPages: 3,
          hasNext: true,
          nextCursor: null,
          metrics: { sourceCount: 12, averageHealthScore: 87, usableCount: 9, warningCount: 3, missingDateCount: 1, waitingCount: 2 }
        });
      })
    });

    render(<HealthView api={api} />);

    expect(await screen.findByText("Source A")).toBeInTheDocument();
    expect(screen.getByText("87")).toBeInTheDocument();
    expect(api.listSourceDiagnosticsPage).toHaveBeenCalledWith(expect.objectContaining({ channel: "ai", pageSize: 50 }));
    fireEvent.change(screen.getByLabelText("健康状态"), { target: { value: "usable" } });
    await waitFor(() => expect(api.listSourceDiagnosticsPage).toHaveBeenCalledWith(expect.objectContaining({ diagnosticStatus: "usable" })));
    await userEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(await screen.findByText("Source B")).toBeInTheDocument();
  });
});
