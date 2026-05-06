import { useCallback, useEffect, useState } from "react";
import { useApi } from "./useApi";
import type { DiscoveryFeed } from "../types";

// Poll the feed-health endpoint every this-many ms so the sidebar counts
// (items_24h_count) stay in sync with whatever the backend poller has just
// ingested. Without this, the sidebar shows stale zeros after a fresh feed
// is added — items appear in the main pane on filter click (that view
// refetches on filter change) but the sidebar count is fetched once at
// mount and never moves.
const FEEDS_POLL_INTERVAL_MS = 30_000;

export function useDiscoveryFeeds() {
  const { request, authReady } = useApi();
  const [feeds, setFeeds] = useState<DiscoveryFeed[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
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
    if (!authReady) return;
    // First fetch flips `loading` off when it returns; subsequent polls
    // refresh data silently so the sidebar counts and FeedsHealth view
    // don't flash through a "Loading…" state every 30 s.
    void refresh();
    const id = window.setInterval(() => void refresh(), FEEDS_POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [authReady, refresh]);

  return { feeds, loading, refresh };
}
