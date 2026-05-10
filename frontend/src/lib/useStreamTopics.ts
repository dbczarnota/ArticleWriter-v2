import { useState, useEffect, useCallback } from "react";
import { useApi } from "./useApi";
import type { StreamTopic } from "../types";

const POLL_MS = 30_000;
const PAGE_SIZE = 50;

export function useStreamTopics(subscriptionId?: string | null) {
  const { request, authReady } = useApi();
  const [topics, setTopics] = useState<StreamTopic[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);

  function buildUrl(offset: number): string {
    const params = new URLSearchParams();
    if (subscriptionId) params.set("subscription_id", subscriptionId);
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
  }, [request, subscriptionId]);

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
  }, [request, subscriptionId, topics.length, hasMore, loadingMore]);

  useEffect(() => {
    if (!authReady) return;
    setLoading(true);
    void refresh();
    const id = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(id);
  }, [authReady, refresh]);

  return { topics, loading, loadingMore, hasMore, refresh, loadMore };
}
