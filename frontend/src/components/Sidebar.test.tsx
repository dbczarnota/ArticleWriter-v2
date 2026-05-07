import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Sidebar } from "./Sidebar";
import type { ArticleListItem } from "../types";

vi.mock("../i18n", () => ({
  useT: () => ({
    sidebar: {
      articles: "Articles",
      newArticle: "+ New",
      filterAll: "All",
      filterUndone: "Undone",
      filterDone: "Done",
      filterMine: "Mine",
      filterDates: "Dates",
      dateFrom: "From",
      dateTo: "To",
      clearDates: "Clear",
      noArticles: "No articles",
      noArticlesInRange: "No articles in range",
      loadMore: "Load more",
      loadingMore: "Loading…",
      mine: "Mine",
    },
    datePicker: {
      today: "Today",
      yesterday: "Yesterday",
      thisWeek: "This week",
      last7: "Last 7",
      lastWeek: "Last week",
      thisMonth: "This month",
      last30: "Last 30",
      lastMonth: "Last month",
      apply: "Apply",
      cancel: "Cancel",
      clear: "Clear",
      from: "From",
      to: "To",
    },
  }),
  useLang: () => ({ lang: "en", setLang: () => {} }),
}));

const baseArticle = (over: Partial<ArticleListItem>): ArticleListItem =>
  ({
    id: over.id ?? "x",
    topic: over.topic ?? "T",
    status: over.status ?? "done",
    domain_name: "styl_fm",
    created_at: "2026-05-07T10:00:00Z",
    marked_done: over.marked_done ?? false,
    author_user_id: over.author_user_id ?? "u1",
    author_name: null,
    author_email: null,
    ...over,
  }) as ArticleListItem;

describe("Sidebar filters", () => {
  it("'Done' filter only shows marked_done=true", () => {
    const arts = [
      baseArticle({ id: "a", topic: "Done one", marked_done: true }),
      baseArticle({ id: "b", topic: "Undone one", marked_done: false }),
    ];
    render(
      <Sidebar
        articles={arts}
        selectedId={null}
        onSelect={() => {}}
        onNew={() => {}}
        currentUserId="u1"
        dateRange={{ from: null, to: null }}
        isFiltered={false}
        hasMore={false}
        loadingMore={false}
        onDateRangeChange={() => {}}
        onLoadMore={() => {}}
        open
        isMobile={false}
        onClose={() => {}}
        onExpand={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(screen.getByText("Done one")).toBeInTheDocument();
    expect(screen.queryByText("Undone one")).toBeNull();
  });

  it("'Mine' shows only current user's articles", () => {
    const arts = [
      baseArticle({ id: "a", topic: "Mine one", author_user_id: "u1" }),
      baseArticle({ id: "b", topic: "Other's", author_user_id: "u2" }),
    ];
    render(
      <Sidebar
        articles={arts}
        selectedId={null}
        onSelect={() => {}}
        onNew={() => {}}
        currentUserId="u1"
        dateRange={{ from: null, to: null }}
        isFiltered={false}
        hasMore={false}
        loadingMore={false}
        onDateRangeChange={() => {}}
        onLoadMore={() => {}}
        open
        isMobile={false}
        onClose={() => {}}
        onExpand={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Mine" }));
    expect(screen.getByText("Mine one")).toBeInTheDocument();
    expect(screen.queryByText("Other's")).toBeNull();
  });
});
