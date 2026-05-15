import { useState, useRef, useCallback, useEffect } from "react";
import { useApi } from "../../lib/useApi";

export type JobStatus = "idle" | "submitting" | "waiting" | "done" | "error";

export interface JobResult {
  url: string | null;
  error: string | null;
}

export function useImageCreatorJob() {
  const { request } = useApi();
  const [status, setStatus] = useState<JobStatus>("idle");
  const [result, setResult] = useState<JobResult>({ url: null, error: null });
  const esRef = useRef<EventSource | null>(null);

  const submit = useCallback(
    async (html: string, articleId: string | null, templateName: string) => {
      setStatus("submitting");
      setResult({ url: null, error: null });
      try {
        const { job_id } = await request<{ job_id: string }>(
          "/v2/tools/image-creator/jobs",
          {
            method: "POST",
            body: JSON.stringify({ html, article_id: articleId, template_name: templateName }),
          }
        );
        setStatus("waiting");
        const es = new EventSource(`/v2/tools/image-creator/jobs/${job_id}/stream`);
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
    [request]
  );

  const reset = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setStatus("idle");
    setResult({ url: null, error: null });
  }, []);

  useEffect(() => {
    return () => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, []);

  return { status, result, submit, reset };
}
