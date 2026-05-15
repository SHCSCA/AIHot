import { describe, expect, it, vi } from "vitest";
import { AdminApi, ApiError, AuthApi, PublicApi, buildBasicAuthHeader } from "./api";

describe("AdminApi", () => {
  it("builds a Basic Auth header", () => {
    expect(buildBasicAuthHeader({ username: "admin", password: "secret" })).toBe("Basic YWRtaW46c2VjcmV0");
  });

  it("sends cookie credentials when listing sources", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ sources: [] })
    });
    vi.stubGlobal("fetch", fetchMock);

    await new AdminApi().listSources();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/internal/sources?take=200",
      expect.objectContaining({
        credentials: "include",
        headers: expect.not.objectContaining({ Authorization: expect.any(String) })
      })
    );
  });

  it("uses cookie sessions rather than Basic Auth for RBAC admin calls", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ sources: [] })
    });
    vi.stubGlobal("fetch", fetchMock);

    await new AdminApi().listSources();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/internal/sources?take=200",
      expect.objectContaining({
        credentials: "include",
        headers: expect.not.objectContaining({ Authorization: expect.any(String) })
      })
    );
  });

  it("can patch source enabled state", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ source: { id: "openai_news", enabled: false } })
    });
    vi.stubGlobal("fetch", fetchMock);

    const source = await new AdminApi().patchSource("openai_news", {
      enabled: false
    });

    expect(source.enabled).toBe(false);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/internal/sources/openai_news",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ enabled: false }) })
    );
  });

  it("uses session credentials for productized admin endpoints", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        metrics: {},
        events: [],
        dailyDigests: [],
        pipelineRun: { id: "1" }
      })
    });
    vi.stubGlobal("fetch", fetchMock);
    const api = new AdminApi();

    await api.getDashboard();
    await api.getQualityDashboard({ window: 24 });
    await api.listEvents({ reviewStatus: "pending" });
    await api.generateDailyDigest({ channel: "ai", date: "2026-05-11", strategyVersion: "ai-default-v1" });
    await api.createPipelineRun({ workerId: "manual-worker", limit: 5 });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/internal/dashboard",
      expect.objectContaining({
        credentials: "include",
        headers: expect.not.objectContaining({ Authorization: expect.any(String) })
      })
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/internal/quality-dashboard?window=24",
      expect.objectContaining({
        credentials: "include",
        headers: expect.not.objectContaining({ Authorization: expect.any(String) })
      })
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/internal/events?reviewStatus=pending",
      expect.objectContaining({ method: undefined })
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/internal/daily-digests/generate",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ channel: "ai", date: "2026-05-11", strategyVersion: "ai-default-v1" })
      })
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/internal/pipeline-runs",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ workerId: "manual-worker", limit: 5 }) })
    );
  });

  it("throws an ApiError with status for unauthorized responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: "Unauthorized" })
      })
    );
    const onUnauthorized = vi.fn();

    await expect(new AdminApi("", onUnauthorized).getDashboard()).rejects.toBeInstanceOf(
      ApiError
    );

    expect(onUnauthorized).toHaveBeenCalledOnce();
  });
});

describe("AuthApi", () => {
  it("logs in with a session cookie and loads the current user", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ user: { username: "admin" }, roles: ["admin"], permissions: ["users.manage"] })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ user: { username: "admin" }, roles: ["admin"], permissions: ["users.manage"] })
      });
    vi.stubGlobal("fetch", fetchMock);

    const api = new AuthApi();
    await api.login({ username: "admin", password: "secret" });
    const me = await api.me();

    expect(me.roles).toEqual(["admin"]);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/login",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({ username: "admin", password: "secret" })
      })
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/me",
      expect.objectContaining({ credentials: "include" })
    );
  });
});

describe("PublicApi", () => {
  it("lists public source wall entries without Basic Auth", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ sources: [{ id: "openai_social", sourceGroup: "social" }] })
    });
    vi.stubGlobal("fetch", fetchMock);

    const sources = await new PublicApi().listSources({ channel: "ai", sourceGroup: "social" });

    expect(sources[0].id).toBe("openai_social");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/public/sources?channel=ai&sourceGroup=social",
      expect.objectContaining({ headers: expect.not.objectContaining({ Authorization: expect.any(String) }) })
    );
  });

  it("submits public feedback without Basic Auth", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ feedbackEvent: { id: "1", actor: "public-user" } })
    });
    vi.stubGlobal("fetch", fetchMock);

    await new PublicApi().submitFeedback({
      channel: "ai",
      clusterId: "1",
      feedbackType: "false_positive",
      reason: "内容不相关"
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/public/feedback-events",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          channel: "ai",
          clusterId: "1",
          feedbackType: "false_positive",
          reason: "内容不相关"
        }),
        headers: expect.not.objectContaining({ Authorization: expect.any(String) })
      })
    );
  });
});
