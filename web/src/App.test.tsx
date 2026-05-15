import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AdminApi } from "./api";
import { SourcesView } from "./App";

describe("SourcesView", () => {
  it("renders sources and toggles enabled state", async () => {
    const api = {
      listSourcesPage: vi.fn().mockResolvedValue({
        items: [
          {
            id: "openai_news",
            channel: "ai",
            sourceType: "html",
            tier: "T1",
            name: "OpenAI News",
            url: "https://openai.com/news/",
            language: "en",
            region: "global",
            authorityWeight: 95,
            noiseLevel: 0.05,
            fetchAdapter: "http_article",
            parserType: "website",
            defaultCategories: ["ai_models"],
            fetchIntervalMinutes: 360,
            enabled: true,
            visibility: "public"
          }
        ],
        count: 1,
        hasNext: false,
        nextCursor: null
      }),
      patchSource: vi.fn().mockResolvedValue({ id: "openai_news", enabled: false })
    } as unknown as AdminApi;

    render(<SourcesView api={api} />);

    expect((await screen.findAllByText("OpenAI News")).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: "停用" }));

    await waitFor(() => expect(api.patchSource).toHaveBeenCalledWith("openai_news", { enabled: false }));
  });
});
