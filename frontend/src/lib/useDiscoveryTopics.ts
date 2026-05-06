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

export function useDiscoveryTopics(filters: DiscoveryTopicFilters) {
  const { request, authReady } = useApi();
  const [topics, setTopics] = useState<DiscoveryTopicSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const filtersKey = JSON.stringify({
    feedId: filters.feedId ?? null,
    categories: filters.categories ?? [],
    statuses: filters.statuses ?? [],
    sort: filters.sort ?? "last_activity",
  });

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
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
      const rows = await request<DiscoveryTopicSummary[]>(
        `/v2/discovery/topics?${params.toString()}`,
      );
      setTopics(rows);
    } catch (err) {
      console.error("useDiscoveryTopics: request failed", err);
    } finally {
      setLoading(false);
    }
  }, [request, filtersKey]);

  useEffect(() => {
    if (authReady) void refresh();
  }, [authReady, refresh]);

  return { topics, loading, refresh };
}
