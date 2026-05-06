import { useCallback, useEffect, useState } from "react";
import { useApi } from "./useApi";
import type { DiscoveryTopicSummary } from "../types";

export interface DiscoveryTopicFilters {
  feedId?: string | null;
  categories?: string[];
  statuses?: string[];
}

export function useDiscoveryTopics(filters: DiscoveryTopicFilters) {
  const { request, authReady } = useApi();
  const [topics, setTopics] = useState<DiscoveryTopicSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const filtersKey = JSON.stringify({
    feedId: filters.feedId ?? null,
    categories: filters.categories ?? [],
    statuses: filters.statuses ?? [],
  });

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      const parsed = JSON.parse(filtersKey) as {
        feedId: string | null;
        categories: string[];
        statuses: string[];
      };
      if (parsed.feedId) params.set("feed_id", parsed.feedId);
      for (const c of parsed.categories) params.append("category", c);
      for (const s of parsed.statuses) params.append("status", s);
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
