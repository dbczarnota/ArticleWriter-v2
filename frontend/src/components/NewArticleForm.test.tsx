import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NewArticleForm } from "./NewArticleForm";

const mockSubmitArticle = vi.fn();
vi.mock("../lib/useArticles", () => ({
  useArticles: () => ({ submitArticle: mockSubmitArticle }),
}));
vi.mock("../lib/useApi", () => ({
  useApi: () => ({ request: vi.fn().mockResolvedValue({ article_templates: [] }) }),
}));
vi.mock("../lib/useAuth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "u@e.com", givenName: "Foo", familyName: "Bar" } }),
}));
vi.mock("../i18n", () => ({
  useT: () => ({
    newArticle: {
      heading: "New article",
      topicLabel: "Topic",
      topicPlaceholder: "Topic...",
      instructionsLabel: "Hints",
      instructionsPlaceholder: "Focus on...",
      urlsLabel: "URLs",
      urlsPlaceholder: "One URL per line",
      templateLabel: "Template",
      templateNone: "(none)",
      templateAdHocPlaceholder: "Write template instructions...",
      factsLabel: "Facts",
      factsPlaceholder: "Paste facts...",
      advanced: "Advanced",
      advancedHint: "...",
      headingSettings: "New article — settings",
      settingsButton: "Settings",
      backToBasic: "← Back",
      cancel: "Cancel",
      tabs: {
        topic: "Topic",
        models: "Models",
        search: "Search",
        media: "Media",
        guidelines: "Guidelines",
        html: "HTML",
        reviewer: "Reviewer",
        titles: "Titles",
        articles: "Articles",
      },
      sectionModels: "Models",
      defaultModel: "default",
      fallbacksPlaceholder: "fallbacks",
      sectionSearch: "Search",
      searchFreshness: "Freshness",
      defaultFreshness: "default",
      freshnessHour: "1h",
      freshnessDay: "1d",
      freshnessWeek: "1w",
      freshnessMonth: "1m",
      freshnessYear: "1y",
      articleLength: "Length",
      articleLengthPlaceholder: "len",
      numQueries: "Queries",
      numQueriesPlaceholder: "queries",
      maxResults: "Max results",
      maxResultsPlaceholder: "max",
      maxFacts: "Max facts",
      maxFactsPlaceholder: "facts",
      maxQuotes: "Max quotes",
      maxQuotesPlaceholder: "quotes",
      minSourceSignals: "Min signals",
      minSourceSignalsPlaceholder: "min",
      maxPages: "Max pages",
      maxPagesPlaceholder: "pages",
      contextArticles: "Context articles",
      contextArticlesPlaceholder: "ctx",
      sectionMedia: "Media",
      defaultMedia: "default",
      yes: "yes",
      no: "no",
      mediaLanguages: "Media langs",
      mediaLanguagesPlaceholder: "langs",
      mediaNumResults: "Media results",
      mediaNumResultsPlaceholder: "results",
      mediaMaxTiers: "Max tiers",
      mediaMaxTiersPlaceholder: "tiers",
      youtubeSortByDate: "yt date",
      sectionGuidelines: "Guidelines",
      guidelinesPlaceholder: "guidelines",
      sectionHtml: "HTML",
      htmlPlaceholder: "html",
      sectionReviewer: "Reviewer",
      reviewerRounds: "Rounds",
      reviewerInstructions: "Reviewer instructions",
      reviewerInstructionsPlaceholder: "instr",
      sectionTitles: "Titles",
      titlePlaceholder: "title",
      sectionArticles: "Articles",
      articlePlaceholder: "article",
      addButton: "+ Add",
      generating: "Generating",
      generate: "Generate",
    },
    agents: {
      search: "Search",
      scraping: "Scraping",
      parsing: "Parsing",
      extraction: "Extraction",
      adaptive_search: "Adaptive",
      instructions: "Instructions",
      writer: "Writer",
      reflection: "Reflection",
      followup: "Followup",
    },
    agentTips: { search: "", scraping: "", parsing: "", extraction: "", adaptive_search: "", instructions: "", writer: "", reflection: "", followup: "" },
  }),
}));

beforeEach(() => mockSubmitArticle.mockReset());

describe("NewArticleForm", () => {
  it("splits URLs textarea by newline and posts to /v2/write_article", async () => {
    mockSubmitArticle.mockResolvedValueOnce({ id: "art-123" });
    const onCreated = vi.fn();
    render(<NewArticleForm onCreated={onCreated} />);

    await userEvent.type(screen.getByPlaceholderText("Topic..."), "My topic");
    await userEvent.type(
      screen.getByPlaceholderText("One URL per line"),
      "https://a.com/x{enter}https://b.com/y",
    );
    await userEvent.click(screen.getByRole("button", { name: /^Generate$/ }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("art-123"));
    const body = mockSubmitArticle.mock.calls[0][0];
    expect(body.topic).toBe("My topic");
    expect(body.urls).toEqual(["https://a.com/x", "https://b.com/y"]);
  });

  it("does not submit when topic is empty", async () => {
    render(<NewArticleForm onCreated={() => {}} />);
    // The Generate button is disabled when topic is empty (disabled={loading || !topic.trim()}).
    const btn = screen.getByRole("button", { name: /^Generate$/ });
    expect(btn).toBeDisabled();
    await userEvent.click(btn);
    expect(mockSubmitArticle).not.toHaveBeenCalled();
  });
});
