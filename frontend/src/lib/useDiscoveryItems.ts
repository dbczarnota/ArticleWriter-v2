import { useCallback, useEffect, useState } from "react";
import { useApi } from "./useApi";
import type { DiscoveryItem } from "../types";

export interface DiscoveryItemFilters {
  feedId?: string | null;
  categories?: string[];
}

const PAGE_SIZE = 50;

export function useDiscoveryItems(filters: DiscoveryItemFilters) {
  const { request, authReady } = useApi();
  const [items, setItems] = useState<DiscoveryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);

  const filtersKey = JSON.stringify({
    feedId: filters.feedId ?? null,
    categories: filters.categories ?? [],
  });

  function buildUrl(offset: number): string {
    const params = new URLSearchParams();
    const parsed = JSON.parse(filtersKey) as {
      feedId: string | null;
      categories: string[];
    };
    if (parsed.feedId) params.set("feed_id", parsed.feedId);
    for (const c of parsed.categories) params.append("category", c);
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(offset));
    return `/v2/discovery/items?${params.toString()}`;
  }

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await request<DiscoveryItem[]>(buildUrl(0));
      setItems(rows);
      setHasMore(rows.length === PAGE_SIZE);
    } catch (err) {
      console.error("useDiscoveryItems: request failed", err);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request, filtersKey]);

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const rows = await request<DiscoveryItem[]>(buildUrl(items.length));
      setItems((prev) => [...prev, ...rows]);
      setHasMore(rows.length === PAGE_SIZE);
    } catch (err) {
      console.error("useDiscoveryItems: loadMore failed", err);
    } finally {
      setLoadingMore(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request, filtersKey, items.length, hasMore, loadingMore]);

  useEffect(() => {
    if (authReady) void refresh();
  }, [authReady, refresh]);

  return { items, loading, loadingMore, hasMore, refresh, loadMore };
}
