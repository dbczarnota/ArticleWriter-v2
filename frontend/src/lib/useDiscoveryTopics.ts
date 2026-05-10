import { useCallback, useEffect, useState } from "react";
import { useApi } from "./useApi";
import type { DiscoveryTopicSummary } from "../types";

export type DiscoveryTopicSort = "last_activity" | "first_seen" | "item_count";

export interface DiscoveryTopicFilters {
  feedId?: string | null;
  categories?: string[];
  statuses?: string[];
  sort?: DiscoveryTopicSort;
}

const PAGE_SIZE = 50;

export function useDiscoveryTopics(filters: DiscoveryTopicFilters) {
  const { request, authReady } = useApi();
  const [topics, setTopics] = useState<DiscoveryTopicSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);

  const filtersKey = JSON.stringify({
    feedId: filters.feedId ?? null,
    categories: filters.categories ?? [],
    statuses: filters.statuses ?? [],
    sort: filters.sort ?? "last_activity",
  });

  function buildUrl(offset: number): string {
    const params = new URLSearchParams();
    const parsed = JSON.parse(filtersKey) as {
      feedId: string | null;
      categories: string[];
      statuses: string[];
      sort: DiscoveryTopicSort;
    };
    if (parsed.feedId) params.set("feed_id", parsed.feedId);
    for (const c of parsed.categories) params.append("category", c);
    for (const s of parsed.statuses) params.append("status", s);
    params.set("sort", parsed.sort);
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(offset));
    return `/v2/discovery/topics?${params.toString()}`;
  }

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await request<DiscoveryTopicSummary[]>(buildUrl(0));
      setTopics(rows);
      setHasMore(rows.length === PAGE_SIZE);
    } catch (err) {
      console.error("useDiscoveryTopics: request failed", err);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request, filtersKey]);

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const rows = await request<DiscoveryTopicSummary[]>(buildUrl(topics.length));
      setTopics((prev) => [...prev, ...rows]);
      setHasMore(rows.length === PAGE_SIZE);
    } catch (err) {
      console.error("useDiscoveryTopics: loadMore failed", err);
    } finally {
      setLoadingMore(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request, filtersKey, topics.length, hasMore, loadingMore]);

  useEffect(() => {
    if (authReady) void refresh();
  }, [authReady, refresh]);

  return { topics, loading, loadingMore, hasMore, refresh, loadMore };
}
