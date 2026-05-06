import { useMemo, useState } from "react";
import { useDiscoveryFeeds } from "../lib/useDiscoveryFeeds";
import { useDiscoveryTopics } from "../lib/useDiscoveryTopics";
import { useDiscoveryItems } from "../lib/useDiscoveryItems";
import { useApi } from "../lib/useApi";
import {
  DiscoveryFiltersSidebar,
  type DiscoveryFiltersValue,
} from "./DiscoveryFiltersSidebar";
import { TopicsList } from "./TopicsList";
import { ItemsTable } from "./ItemsTable";
import { FeedsHealth } from "./FeedsHealth";

type DiscoveryView = "topics" | "items" | "feeds";

export function DiscoveryHub() {
  const [view, setView] = useState<DiscoveryView>("topics");
  const [filters, setFilters] = useState<DiscoveryFiltersValue>({
    feedId: null,
    categories: [],
    statuses: ["open", "resurfaced"],
  });

  const { feeds, loading: feedsLoading } = useDiscoveryFeeds();
  const { topics, loading: topicsLoading } = useDiscoveryTopics({
    feedId: filters.feedId,
    categories: filters.categories,
    statuses: filters.statuses,
  });
  const { items, loading: itemsLoading } = useDiscoveryItems({
    feedId: filters.feedId,
    categories: filters.categories,
  });
  const { request } = useApi();

  // Build the category list from whatever the user has visible right now.
  // Backend has no "list categories with counts" endpoint, and the existing
  // /discovery/categories endpoint returns just names — driving the sidebar
  // off the current topic/item set keeps the UI honest about what's selectable.
  const availableCategories = useMemo(() => {
    const set = new Set<string>();
    for (const t of topics) for (const c of t.categories) set.add(c);
    for (const it of items) for (const c of it.categories) set.add(c);
    return Array.from(set).sort().map((name) => ({ name }));
  }, [topics, items]);

  async function startWrite(topicId: string) {
    const resp = await request<{ article_id: string }>(
      `/v2/discovery/topics/${topicId}/write_article`,
      { method: "POST" }
    );
    // Hand off to App.tsx, which owns the View state and selectedArticleId.
    // We use a window CustomEvent to keep DiscoveryHub decoupled from the
    // App-level view router.
    window.dispatchEvent(
      new CustomEvent("discovery:open-article", { detail: { articleId: resp.article_id } })
    );
  }

  const tabBtn = (active: boolean): React.CSSProperties => ({
    padding: "6px 12px",
    background: active ? "var(--accent-lt)" : "transparent",
    border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
    borderRadius: "var(--radius)",
    color: active ? "var(--accent)" : "var(--text)",
    cursor: active ? "default" : "pointer",
    fontSize: 13,
    fontWeight: active ? 600 : 400,
  });

  return (
    <div style={{ display: "flex", height: "100%", background: "var(--bg)" }}>
      <DiscoveryFiltersSidebar
        feeds={feeds}
        availableCategories={availableCategories}
        value={filters}
        onChange={setFilters}
      />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <div
          style={{
            borderBottom: "1px solid var(--border)",
            padding: "12px 24px",
            display: "flex",
            gap: 8,
            background: "var(--white)",
          }}
        >
          <button type="button" onClick={() => setView("topics")} disabled={view === "topics"} style={tabBtn(view === "topics")}>
            📚 Tematy
          </button>
          <button type="button" onClick={() => setView("items")} disabled={view === "items"} style={tabBtn(view === "items")}>
            📰 Itemy
          </button>
          <button type="button" onClick={() => setView("feeds")} disabled={view === "feeds"} style={tabBtn(view === "feeds")}>
            🔌 Feedy
          </button>
        </div>
        <div style={{ flex: 1, overflow: "auto", background: "var(--bg)" }}>
          {view === "topics" && (
            <TopicsList topics={topics} loading={topicsLoading} onWrite={startWrite} />
          )}
          {view === "items" && <ItemsTable items={items} loading={itemsLoading} />}
          {view === "feeds" && <FeedsHealth feeds={feeds} loading={feedsLoading} />}
        </div>
      </div>
    </div>
  );
}
