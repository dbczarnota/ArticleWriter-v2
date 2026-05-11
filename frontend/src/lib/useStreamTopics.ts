import { useState, useEffect, useCallback } from "react";
import { useApi } from "./useApi";
import type { StreamTopic } from "../types";

export type StreamTopicSort = "last_seen" | "first_seen";

const PAGE_SIZE = 50;

export function useStreamTopics(subscriptionId?: string | null, sort: StreamTopicSort = "last_seen") {
  const { request, authReady } = useApi();
  const [topics, setTopics] = useState<StreamTopic[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);

  const paramsKey = JSON.stringify({ subscriptionId: subscriptionId ?? null, sort });

  function buildUrl(offset: number): string {
    const { subscriptionId: sid, sort: s } = JSON.parse(paramsKey) as { subscriptionId: string | null; sort: StreamTopicSort };
    const params = new URLSearchParams();
    if (sid) params.set("subscription_id", sid);
    params.set("sort", s);
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(offset));
    return `/v2/streams/topics?${params.toString()}`;
  }

  const refresh = useCallback(async () => {
    try {
      const rows = await request<StreamTopic[]>(buildUrl(0));
      setTopics(rows);
      setHasMore(rows.length === PAGE_SIZE);
    } catch (err) {
      console.error("useStreamTopics: request failed", err);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request, paramsKey]);

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const rows = await request<StreamTopic[]>(buildUrl(topics.length));
      setTopics((prev) => [...prev, ...rows]);
      setHasMore(rows.length === PAGE_SIZE);
    } catch (err) {
      console.error("useStreamTopics: loadMore failed", err);
    } finally {
      setLoadingMore(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request, paramsKey, topics.length, hasMore, loadingMore]);

  useEffect(() => {
    if (!authReady) return;
    setLoading(true);
    void refresh();
  }, [authReady, refresh]);

  return { topics, loading, loadingMore, hasMore, refresh, loadMore };
}
