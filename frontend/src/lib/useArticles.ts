import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useApi } from "./useApi";
import type { Article, ArticleListItem } from "../types";

const PAGE_SIZE = 100;

/** ISO date strings 'YYYY-MM-DD' (matching native <input type="date">), or null. */
export interface DateRange {
  from: string | null;
  to: string | null;
}

/** Initial filter on first session load — Last 7 days, computed inline to
 * keep this hook self-contained. The picker has its own copy of the same
 * preset logic in lib/datePresets.ts. */
function defaultLast7DaysRange(): DateRange {
  const t = new Date();
  const today = new Date(t.getFullYear(), t.getMonth(), t.getDate());
  const start = new Date(today);
  start.setDate(start.getDate() - 6);
  const fmt = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return { from: fmt(start), to: fmt(today) };
}

function buildArticlesUrl(offset: number, range: DateRange): string {
  const params = new URLSearchParams({
    limit: String(PAGE_SIZE),
    offset: String(offset),
  });
  if (range.from) {
    // Inclusive start of day in UTC.
    params.set("created_after", `${range.from}T00:00:00Z`);
  }
  if (range.to) {
    // Inclusive end of day in UTC so the user gets a full calendar day.
    params.set("created_before", `${range.to}T23:59:59Z`);
  }
  return `/v2/articles?${params.toString()}`;
}

export function useArticles() {
  const { request, authReady } = useApi();
  const [articles, setArticles] = useState<ArticleListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [dateRange, setDateRangeState] = useState<DateRange>(defaultLast7DaysRange);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isFiltered = useMemo(
    () => Boolean(dateRange.from) || Boolean(dateRange.to),
    [dateRange],
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await request<ArticleListItem[]>(buildArticlesUrl(0, dateRange));
      setArticles(data);
      setHasMore(data.length === PAGE_SIZE);
      return data;
    } finally {
      setLoading(false);
    }
  }, [request, dateRange]);

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const data = await request<ArticleListItem[]>(
        buildArticlesUrl(articles.length, dateRange),
      );
      setArticles((prev) => [...prev, ...data]);
      setHasMore(data.length === PAGE_SIZE);
    } finally {
      setLoadingMore(false);
    }
  }, [request, articles.length, dateRange, hasMore, loadingMore]);

  const setDateRange = useCallback((next: DateRange) => {
    // Changing the filter resets pagination — refresh effect picks it up.
    setDateRangeState(next);
  }, []);

  useEffect(() => { if (authReady) refresh(); }, [authReady, refresh]);

  // Poll every 4 s while any article is still running
  useEffect(() => {
    const hasRunning = articles.some((a) => a.status === "running");
    if (hasRunning && !pollingRef.current) {
      pollingRef.current = setInterval(() => { refresh(); }, 4000);
    } else if (!hasRunning && pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [articles, refresh]);

  // Refresh whenever the tab becomes visible again. The 4s poll only runs while
  // an article is `running`; once everything is done the list goes stale until
  // the user hits F5 or generates a new article. Switching tabs and coming
  // back is the most common "did anything change?" signal — hook into it.
  useEffect(() => {
    if (!authReady) return;
    const onVisibility = () => {
      if (document.visibilityState === "visible") refresh();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [authReady, refresh]);

  async function fetchArticle(id: string): Promise<Article> {
    return request<Article>(`/v2/articles/${id}`);
  }

  async function markDone(id: string, done: boolean, byName?: string): Promise<void> {
    await request<{ ok: boolean }>(`/v2/articles/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ marked_done: done, marked_done_by_name: done ? (byName ?? null) : null }),
    });
    setArticles((prev) => prev.map((a) => a.id === id ? { ...a, marked_done: done } : a));
  }

  async function submitArticle(body: {
    topic: string;
    additional_instructions?: string;
    urls?: string[];
    agents?: Record<string, Record<string, unknown>>;
    domain_overrides?: Record<string, unknown>;
    author_name?: string;
    raw_facts_text?: string;
    article_template?: string;
  }): Promise<Article> {
    return request<Article>("/v2/write_article", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  return {
    articles,
    loading,
    loadingMore,
    hasMore,
    dateRange,
    isFiltered,
    refresh,
    loadMore,
    setDateRange,
    fetchArticle,
    submitArticle,
    markDone,
  };
}
