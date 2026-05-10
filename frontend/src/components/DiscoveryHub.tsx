import { useMemo, useState } from "react";
import { useDiscoveryFeeds } from "../lib/useDiscoveryFeeds";
import { useDiscoveryTopics, type DiscoveryTopicSort } from "../lib/useDiscoveryTopics";
import { useDiscoveryItems } from "../lib/useDiscoveryItems";
import { useApi } from "../lib/useApi";
import {
  DiscoveryFiltersSidebar,
  type DiscoveryFiltersValue,
} from "./DiscoveryFiltersSidebar";
import { TopicsList } from "./TopicsList";
import { ItemsTable } from "./ItemsTable";
import { FeedsHealth } from "./FeedsHealth";
import { TopicDetail } from "./TopicDetail";
import { WriteFromTopicDialog } from "./WriteFromTopicDialog";
import { useT } from "../i18n";
import { TopicsIcon, ItemsIcon, FeedsIcon, StreamsIcon, StreamTopicsIcon } from "./ui/icons";
import { useStreamSubscriptions } from "../lib/useStreamSubscriptions";
import { useStreamTopics } from "../lib/useStreamTopics";
import { StreamsHealth } from "./StreamsHealth";
import { StreamTopicsList } from "./StreamTopicsList";

type DiscoveryView = "topics" | "items" | "feeds" | "streamy" | "tematy-streamow";

export function DiscoveryHub() {
  const t = useT();
  const [view, setView] = useState<DiscoveryView>("topics");
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const [writeFromTopicId, setWriteFromTopicId] = useState<string | null>(null);
  const [filters, setFilters] = useState<DiscoveryFiltersValue>({
    feedId: null,
    categories: [],
    statuses: ["open", "resurfaced"],
  });
  const [sort, setSort] = useState<DiscoveryTopicSort>("item_count");
  const [pendingTopicAction, setPendingTopicAction] = useState<string | null>(null);

  const { feeds, loading: feedsLoading } = useDiscoveryFeeds();
  const { topics, loading: topicsLoading, refresh: refreshTopics } = useDiscoveryTopics({
    feedId: filters.feedId,
    categories: filters.categories,
    statuses: filters.statuses,
    sort,
  });
  const { request } = useApi();
  const { items, loading: itemsLoading } = useDiscoveryItems({
    feedId: filters.feedId,
    categories: filters.categories,
  });
  const { subscriptions, loading: subsLoading, remove: removeSub } = useStreamSubscriptions();
  const { topics: streamTopics, loading: streamTopicsLoading } = useStreamTopics();
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

  function startWrite(topicId: string) {
    // Open the pre-write dialog so the editor can review the title and
    // toggle source URLs before the pipeline kicks off. The actual POST
    // happens inside the dialog on Generate.
    setWriteFromTopicId(topicId);
  }

  async function dismissTopic(topicId: string) {
    setPendingTopicAction(topicId);
    try {
      await request(`/v2/discovery/topics/${topicId}/dismiss`, { method: "POST" });
      await refreshTopics();
    } catch (err) {
      console.error("DiscoveryHub: dismiss failed", err);
    } finally {
      setPendingTopicAction(null);
    }
  }

  async function restoreTopic(topicId: string) {
    setPendingTopicAction(topicId);
    try {
      await request(`/v2/discovery/topics/${topicId}/restore`, { method: "POST" });
      await refreshTopics();
    } catch (err) {
      console.error("DiscoveryHub: restore failed", err);
    } finally {
      setPendingTopicAction(null);
    }
  }

  function onArticleSubmitted(articleId: string) {
    setWriteFromTopicId(null);
    // Hand off to App.tsx, which owns the View state and selectedArticleId.
    // We use a window CustomEvent to keep DiscoveryHub decoupled from the
    // App-level view router.
    window.dispatchEvent(
      new CustomEvent("discovery:open-article", { detail: { articleId } })
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
            alignItems: "center",
            background: "var(--white)",
          }}
        >
          <button
            type="button"
            onClick={() => setView("topics")}
            disabled={view === "topics"}
            style={{ ...tabBtn(view === "topics"), display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <TopicsIcon /> {t.discovery.views.topics}
          </button>
          <button
            type="button"
            onClick={() => setView("items")}
            disabled={view === "items"}
            style={{ ...tabBtn(view === "items"), display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <ItemsIcon /> {t.discovery.views.items}
          </button>
          <button
            type="button"
            onClick={() => setView("feeds")}
            disabled={view === "feeds"}
            style={{ ...tabBtn(view === "feeds"), display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <FeedsIcon /> {t.discovery.views.feeds}
          </button>
          <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
            <button
              type="button"
              onClick={() => setView("streamy")}
              disabled={view === "streamy"}
              style={{ ...tabBtn(view === "streamy"), display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <StreamsIcon /> {t.streams.views.subscriptions}
            </button>
            <button
              type="button"
              onClick={() => setView("tematy-streamow")}
              disabled={view === "tematy-streamow"}
              style={{ ...tabBtn(view === "tematy-streamow"), display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <StreamTopicsIcon /> {t.streams.views.topics}
            </button>
          </div>
          {view === "topics" && !selectedTopicId && (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <label htmlFor="discovery-topics-sort" style={{ fontSize: 12, color: "var(--muted)" }}>
                {t.discovery.sort.label}
              </label>
              <select
                id="discovery-topics-sort"
                value={sort}
                onChange={(e) => setSort(e.target.value as DiscoveryTopicSort)}
                style={{
                  padding: "5px 8px",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  background: "var(--white)",
                  color: "var(--text)",
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                <option value="last_activity">{t.discovery.sort.lastActivity}</option>
                <option value="first_seen">{t.discovery.sort.firstSeen}</option>
                <option value="item_count">{t.discovery.sort.itemCount}</option>
              </select>
            </div>
          )}
        </div>
        <div style={{ flex: 1, overflow: "auto", background: "var(--bg)" }}>
          {selectedTopicId ? (
            <TopicDetail
              topicId={selectedTopicId}
              onBack={() => setSelectedTopicId(null)}
              onWrite={startWrite}
            />
          ) : (
            <>
              {view === "topics" && (
                <TopicsList
                  topics={topics}
                  loading={topicsLoading}
                  onWrite={startWrite}
                  onSelect={setSelectedTopicId}
                  onDismiss={dismissTopic}
                  onRestore={restoreTopic}
                  pendingActionId={pendingTopicAction}
                />
              )}
              {view === "items" && <ItemsTable items={items} loading={itemsLoading} />}
              {view === "feeds" && <FeedsHealth feeds={feeds} loading={feedsLoading} />}
              {view === "streamy" && (
                <StreamsHealth
                  subscriptions={subscriptions}
                  loading={subsLoading}
                  onDelete={removeSub}
                />
              )}
              {view === "tematy-streamow" && (
                <StreamTopicsList topics={streamTopics} loading={streamTopicsLoading} />
              )}
            </>
          )}
        </div>
      </div>
      {writeFromTopicId && (
        <WriteFromTopicDialog
          topicId={writeFromTopicId}
          onCancel={() => setWriteFromTopicId(null)}
          onSubmitted={onArticleSubmitted}
        />
      )}
    </div>
  );
}
