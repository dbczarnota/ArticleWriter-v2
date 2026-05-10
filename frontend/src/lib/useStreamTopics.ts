import { useState, useEffect, useCallback } from "react";
import { useApi } from "./useApi";
import type { StreamTopic } from "../types";

const POLL_MS = 30_000;

export function useStreamTopics() {
  const { request, authReady } = useApi();
  const [topics, setTopics] = useState<StreamTopic[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const rows = await request<StreamTopic[]>("/v2/streams/topics");
      setTopics(rows);
    } catch (err) {
      console.error("useStreamTopics: request failed", err);
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    if (!authReady) return;
    void refresh();
    const id = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(id);
  }, [authReady, refresh]);

  return { topics, loading, refresh };
}
