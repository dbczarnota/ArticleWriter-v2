import { useCallback, useEffect, useState } from "react";
import { useApi } from "./useApi";
import type { Article, ArticleListItem } from "../types";

export function useArticles() {
  const { request } = useApi();
  const [articles, setArticles] = useState<ArticleListItem[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await request<ArticleListItem[]>("/v2/articles");
      setArticles(data);
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => { refresh(); }, [refresh]);

  async function fetchArticle(id: string): Promise<Article> {
    return request<Article>(`/v2/articles/${id}`);
  }

  async function submitArticle(body: {
    topic: string;
    additional_instructions?: string;
    urls?: string[];
    agents?: Record<string, Record<string, unknown>>;
  }): Promise<Article> {
    return request<Article>("/v2/write_article", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  return { articles, loading, refresh, fetchArticle, submitArticle };
}
