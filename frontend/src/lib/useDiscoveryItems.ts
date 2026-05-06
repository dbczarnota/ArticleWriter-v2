import { useCallback, useEffect, useState } from "react";
import { useApi } from "./useApi";
import type { DiscoveryItem } from "../types";

export interface DiscoveryItemFilters {
  feedId?: string | null;
  categories?: string[];
}

export function useDiscoveryItems(filters: DiscoveryItemFilters) {
  const { request, authReady } = useApi();
  const [items, setItems] = useState<DiscoveryItem[]>([]);
  const [loading, setLoading] = useState(true);

  const filtersKey = JSON.stringify({
    feedId: filters.feedId ?? null,
    categories: filters.categories ?? [],
  });

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      const parsed = JSON.parse(filtersKey) as {
        feedId: string | null;
        categories: string[];
      };
      if (parsed.feedId) params.set("feed_id", parsed.feedId);
      for (const c of parsed.categories) params.append("category", c);
      const rows = await request<DiscoveryItem[]>(
        `/v2/discovery/items?${params.toString()}`,
      );
      setItems(rows);
    } catch (err) {
      console.error("useDiscoveryItems: request failed", err);
    } finally {
      setLoading(false);
    }
  }, [request, filtersKey]);

  useEffect(() => {
    if (authReady) void refresh();
  }, [authReady, refresh]);

  return { items, loading, refresh };
}
