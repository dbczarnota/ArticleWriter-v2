import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DomainConfigForm } from "./DomainConfigForm";
import type { DomainConfigData } from "../types";

const BASE_CONFIG: DomainConfigData = {
  org_code: "test",
  domain_name: "test",
  description: "",
  language: "pl",
  target_word_count: 600,
  max_facts: 8,
  max_quotes: 3,
  search_freshness: "qdr:w",
  num_queries: 3,
  max_results: 5,
  min_source_signals: 1,
  max_pages_to_scrape: 10,
  youtube_search: false,
  twitter_search: false,
  facebook_search: false,
  news_search: false,
  tiktok_search: false,
  instagram_search: false,
  reddit_search: false,
  media_search_languages: ["en"],
  media_search_num: 5,
  media_search_max_query_tiers: 2,
  youtube_sort_by_date: true,
  reflection_context_articles: 2,
  guidelines: "",
  html_format: "",
  reflection_stance: "",
  reflection_rounds: 1,
  example_articles: [],
  example_titles: [],
  agent_models: {},
  agent_fallback_models: {},
  article_templates: [],
  image_templates: [],
  image_creator_enabled: false,
  discovery_enabled: false,
  discovery_feeds: [],
  discovery_categories: [],
  discovery_topic_matching_window_days: 3,
  discovery_followup_threshold: 5,
  discovery_classifier_model: "google-gla:gemini-flash-lite-latest",
  discovery_matcher_model: "google-gla:gemini-flash-lite-latest",
  discovery_topic_writer_model: "google-gla:gemini-flash-lite-latest",
  discovery_classifier_fallback_models: [],
  discovery_matcher_fallback_models: [],
  discovery_topic_writer_fallback_models: [],
  discovery_retention_days: 14,
  stream_retention_days: 7,
  updated_at: null,
};

function renderFreshness(search_freshness: string) {
  const onSave = vi.fn();
  render(
    <DomainConfigForm
      initialConfig={{ ...BASE_CONFIG, search_freshness }}
      activeSection="wyszukiwanie"
      saving={false}
      error={null}
      onSave={onSave}
    />,
  );
  return { onSave };
}

describe("Świeżość wyników — custom days input", () => {
  it("shows predefined options and no number input for standard value", () => {
    renderFreshness("qdr:w");

    const select = screen.getByRole("combobox");
    expect(select).toHaveValue("qdr:w");
    expect(screen.queryByPlaceholderText("Liczba dni")).toBeNull();
  });

  it("shows 'Własna' option in the select", () => {
    renderFreshness("qdr:w");

    expect(screen.getByRole("option", { name: "Własna (wpisz dni)" })).toBeInTheDocument();
  });

  it("selecting 'Własna' reveals a number input", async () => {
    renderFreshness("qdr:w");

    await userEvent.selectOptions(screen.getByRole("combobox"), "__custom__");

    expect(screen.getByPlaceholderText("Liczba dni")).toBeInTheDocument();
  });

  it("changing the number input updates value to qdr:N", async () => {
    renderFreshness("qdr:w");
    await userEvent.selectOptions(screen.getByRole("combobox"), "__custom__");

    const input = screen.getByPlaceholderText("Liczba dni");
    fireEvent.change(input, { target: { value: "14" } });

    expect((input as HTMLInputElement).value).toBe("14");
  });

  it("renders with existing custom value qdr:14 → select shows 'Własna', input shows 14", () => {
    renderFreshness("qdr:14");

    const select = screen.getByRole("combobox");
    expect(select).toHaveValue("__custom__");

    const input = screen.getByPlaceholderText("Liczba dni") as HTMLInputElement;
    expect(input.value).toBe("14");
  });

  it("switching back to a predefined option hides the number input", async () => {
    renderFreshness("qdr:14");

    await userEvent.selectOptions(screen.getByRole("combobox"), "qdr:m");

    expect(screen.queryByPlaceholderText("Liczba dni")).toBeNull();
  });

  it("save button submits qdr:N when custom days are set", async () => {
    const { onSave } = renderFreshness("qdr:w");

    await userEvent.selectOptions(screen.getByRole("combobox"), "__custom__");
    const input = screen.getByPlaceholderText("Liczba dni");
    fireEvent.change(input, { target: { value: "30" } });

    await userEvent.click(screen.getByRole("button", { name: /zapisz/i }));

    expect(onSave).toHaveBeenCalledOnce();
    expect(onSave.mock.calls[0][0].search_freshness).toBe("qdr:30");
  });
});
