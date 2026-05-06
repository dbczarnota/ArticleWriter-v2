import { useCallback, useEffect, useState } from "react";
import { useApi } from "./useApi";
import type { DiscoveryFeed } from "../types";

export function useDiscoveryFeeds() {
  const { request, authReady } = useApi();
  const [feeds, setFeeds] = useState<DiscoveryFeed[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await request<DiscoveryFeed[]>("/v2/discovery/feeds");
      setFeeds(rows);
    } catch (err) {
      // Don't swallow silently — UI shows "Loading…" → "no feeds" without
      // any signal that the request failed. Surface to console at minimum.
      console.error("useDiscoveryFeeds: request failed", err);
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    if (authReady) void refresh();
  }, [authReady, refresh]);

  return { feeds, loading, refresh };
}
