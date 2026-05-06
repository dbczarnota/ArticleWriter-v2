import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DiscoveryHub } from "./DiscoveryHub";

vi.mock("../lib/useApi", () => ({
  useApi: () => ({ request: vi.fn(async () => ({})), orgCode: "", authReady: true }),
}));
vi.mock("../lib/useDiscoveryFeeds", () => ({
  useDiscoveryFeeds: () => ({ feeds: [], loading: false }),
}));
vi.mock("../lib/useDiscoveryTopics", () => ({
  useDiscoveryTopics: () => ({ topics: [], loading: false }),
}));
vi.mock("../lib/useDiscoveryItems", () => ({
  useDiscoveryItems: () => ({ items: [], loading: false }),
}));
// Lock the i18n locale so test assertions don't depend on the runtime
// language detection (CI may default to en, dev to pl).
vi.mock("../i18n", () => ({
  useT: () => ({
    discovery: {
      views: { topics: "TopicsLabel", items: "ItemsLabel", feeds: "FeedsLabel" },
      filters: { feeds: "Feeds", categories: "Categories", status: "Status", all: "All", emptyCategories: "" },
      status: { open: "open", resurfaced: "resurfaced", consumed: "consumed" },
      topic: { sources: "", write: "", openArticle: "", loading: "", empty: "", backToTopics: "", firstSeen: "", lastActivity: "", statusLabel: "", itemsCount: "", writeArticle: "", itemsShort: "", error: "", toggleSources: "" },
      item: { empty: "", uncategorized: "", colItem: "", colCategories: "", colSeen: "" },
      feed: { lastFetched: "", errors: "", items24h: "", healthy: "", degraded: "", disabled: "", emptyHint: "", lastError: "", justNow: "", minAgo: "", hAgo: "", dAgo: "" },
      hub: { resurfaced: "", written: "", sources: "", sourcesCount: "" },
    },
  }),
}));

describe("DiscoveryHub", () => {
  it("renders the three view tabs", () => {
    render(<DiscoveryHub />);
    expect(screen.getByRole("button", { name: /TopicsLabel/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /ItemsLabel/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /FeedsLabel/ })).toBeInTheDocument();
  });
});
