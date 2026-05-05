import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "./useApi";
import type { Article, ArticleListItem } from "../types";

export function useArticles() {
  const { request, authReady } = useApi();
  const [articles, setArticles] = useState<ArticleListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await request<ArticleListItem[]>("/v2/articles");
      setArticles(data);
      return data;
    } finally {
      setLoading(false);
    }
  }, [request]);

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
  }): Promise<Article> {
    return request<Article>("/v2/write_article", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  return { articles, loading, refresh, fetchArticle, submitArticle, markDone };
}
