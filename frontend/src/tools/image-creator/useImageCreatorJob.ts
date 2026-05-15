import { useState, useRef, useCallback } from "react";
import { useApi } from "../../lib/useApi";

export type JobStatus = "idle" | "submitting" | "waiting" | "done" | "error";

export interface JobResult {
  url: string | null;
  error: string | null;
}

export function useImageCreatorJob() {
  const api = useApi();
  const [status, setStatus] = useState<JobStatus>("idle");
  const [result, setResult] = useState<JobResult>({ url: null, error: null });
  const esRef = useRef<EventSource | null>(null);

  const submit = useCallback(
    async (html: string, articleId: string | null, templateName: string) => {
      setStatus("submitting");
      setResult({ url: null, error: null });
      try {
        const { job_id } = await api.post<{ job_id: string }>(
          "/api/v2/tools/image-creator/jobs",
          { html, article_id: articleId, template_name: templateName }
        );
        setStatus("waiting");
        const es = new EventSource(`/api/v2/tools/image-creator/jobs/${job_id}/stream`);
        esRef.current = es;
        es.onmessage = (e) => {
          const data = JSON.parse(e.data) as { status: string; url?: string; error?: string };
          es.close();
          esRef.current = null;
          if (data.status === "done" && data.url) {
            setResult({ url: data.url, error: null });
            setStatus("done");
          } else {
            setResult({ url: null, error: data.error ?? "Unknown error" });
            setStatus("error");
          }
        };
        es.onerror = () => {
          es.close();
          esRef.current = null;
          setResult({ url: null, error: "Connection lost" });
          setStatus("error");
        };
      } catch (err) {
        setResult({ url: null, error: err instanceof Error ? err.message : "Submit failed" });
        setStatus("error");
      }
    },
    [api]
  );

  const reset = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setStatus("idle");
    setResult({ url: null, error: null });
  }, []);

  return { status, result, submit, reset };
}
