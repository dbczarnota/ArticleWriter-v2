import { useCallback, useState } from "react";
import { useApi } from "./useApi";
import type { DiscoveryTopicDetail } from "../types";

export function useDiscoveryTopicDetail() {
  const { request } = useApi();
  const [cache, setCache] = useState<Record<string, DiscoveryTopicDetail>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  const load = useCallback(
    async (topicId: string): Promise<DiscoveryTopicDetail> => {
      const cached = cache[topicId];
      if (cached) return cached;
      setLoading((m) => ({ ...m, [topicId]: true }));
      try {
        const detail = await request<DiscoveryTopicDetail>(
          `/v2/discovery/topics/${topicId}`,
        );
        setCache((c) => ({ ...c, [topicId]: detail }));
        return detail;
      } finally {
        setLoading((m) => ({ ...m, [topicId]: false }));
      }
    },
    [request, cache],
  );

  return { load, cache, loading };
}
