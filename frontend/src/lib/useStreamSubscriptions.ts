import { useCallback, useEffect, useState } from "react";
import { useApi } from "./useApi";
import type { StreamSubscription } from "../types";

const POLL_MS = 30_000;

export function useStreamSubscriptions() {
  const { request, authReady } = useApi();
  const [subscriptions, setSubscriptions] = useState<StreamSubscription[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const rows = await request<StreamSubscription[]>("/v2/streams/subscriptions");
      setSubscriptions(rows);
    } catch (err) {
      console.error("useStreamSubscriptions: request failed", err);
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

  const create = useCallback(
    async (body: {
      name: string;
      stream_url: string;
      stream_type: string;
      url_refresh_url?: string;
      url_refresh_field?: string;
      chunk_duration_seconds?: number;
    }) => {
      const sub = await request<StreamSubscription>("/v2/streams/subscriptions", {
        method: "POST",
        body: JSON.stringify(body),
      });
      await refresh();
      return sub;
    },
    [request, refresh],
  );

  const remove = useCallback(
    async (id: string) => {
      await request(`/v2/streams/subscriptions/${id}`, { method: "DELETE" });
      await refresh();
    },
    [request, refresh],
  );

  const start = useCallback(
    async (id: string) => {
      await request<StreamSubscription>(`/v2/streams/subscriptions/${id}/start`, {
        method: "POST",
      });
      await refresh();
    },
    [request, refresh],
  );

  const stop = useCallback(
    async (id: string) => {
      await request(`/v2/streams/subscriptions/${id}/stop`, { method: "POST" });
      await refresh();
    },
    [request, refresh],
  );

  return { subscriptions, loading, refresh, create, remove, start, stop };
}
