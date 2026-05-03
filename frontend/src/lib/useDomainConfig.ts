// frontend/src/lib/useDomainConfig.ts
import { useCallback, useEffect, useState } from "react";
import { useApi } from "./useApi";
import type { DomainConfigData } from "../types";

export function useDomainConfig() {
  const { request } = useApi();
  const [config, setConfig] = useState<DomainConfigData | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await request<DomainConfigData>("/v2/domain-config");
      setConfig(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => { load(); }, [load]);

  async function save(updated: DomainConfigData): Promise<void> {
    setSaving(true);
    setError(null);
    try {
      const saved = await request<DomainConfigData>("/v2/domain-config", {
        method: "PUT",
        body: JSON.stringify(updated),
      });
      setConfig(saved);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    } finally {
      setSaving(false);
    }
  }

  return { config, loading, saving, error, save };
}
