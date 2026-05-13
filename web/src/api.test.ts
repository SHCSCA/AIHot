import { describe, expect, it, vi } from "vitest";
import { AdminApi, ApiError, PublicApi, buildBasicAuthHeader } from "./api";

describe("AdminApi", () => {
  it("builds a Basic Auth header", () => {
    expect(buildBasicAuthHeader({ username: "admin", password: "secret" })).toBe("Basic YWRtaW46c2VjcmV0");
  });

  it("sends Basic Auth when listing sources", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ sources: [] })
    });
    vi.stubGlobal("fetch", fetchMock);

    await new AdminApi({ username: "admin", password: "secret" }).listSources();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/internal/sources",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Basic YWRtaW46c2VjcmV0" })
      })
    );
  });

  it("can patch source enabled state", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ source: { id: "openai_news", enabled: false } })
    });
    vi.stubGlobal("fetch", fetchMock);

    const source = await new AdminApi({ username: "admin", password: "secret" }).patchSource("openai_news", {
      enabled: false
    });

    expect(source.enabled).toBe(false);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/internal/sources/openai_news",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ enabled: false }) })
    );
  });

  it("uses Basic Auth for productized admin endpoints", async () => {
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
    const api = new AdminApi({ username: "admin", password: "secret" });

    await api.getDashboard();
    await api.listEvents({ reviewStatus: "pending" });
    await api.generateDailyDigest({ channel: "ai", date: "2026-05-11", strategyVersion: "ai-default-v1" });
    await api.createPipelineRun({ workerId: "manual-worker", limit: 5 });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/internal/dashboard",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Basic YWRtaW46c2VjcmV0" })
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

    await expect(new AdminApi({ username: "bad", password: "bad" }, "", onUnauthorized).getDashboard()).rejects.toBeInstanceOf(
      ApiError
    );

    expect(onUnauthorized).toHaveBeenCalledOnce();
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
