import { useEffect, useRef, useState } from "react";
import type { DiscoveryTopicDetail } from "../types";
import { useApi } from "../lib/useApi";
import { useT } from "../i18n";

interface Props {
  topicId: string;
  onCancel: () => void;
  onSubmitted: (articleId: string) => void;
}

export function WriteFromTopicDialog({ topicId, onCancel, onSubmitted }: Props) {
  const t = useT();
  const { request } = useApi();
  const [detail, setDetail] = useState<DiscoveryTopicDetail | null>(null);
  const [topicTitle, setTopicTitle] = useState("");
  const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => () => { mounted.current = false; }, []);

  useEffect(() => {
    let cancelled = false;
    void request<DiscoveryTopicDetail>(`/v2/discovery/topics/${topicId}`).then((d) => {
      if (cancelled) return;
      setDetail(d);
      setTopicTitle(d.title);
      setSelectedUrls(new Set(d.items.map((it) => it.canonical_url)));
    });
    return () => { cancelled = true; };
  }, [request, topicId]);

  function toggleUrl(url: string) {
    setSelectedUrls((prev) => {
      const next = new Set(prev);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return next;
    });
  }

  async function copyTitle(title: string) {
    try {
      await navigator.clipboard.writeText(title);
      setCopiedUrl(title);
      setTimeout(() => mounted.current && setCopiedUrl(null), 1500);
    } catch {
      // clipboard blocked — silent fallback (the title is still visible)
    }
  }

  async function submit() {
    if (!detail) return;
    setSubmitting(true);
    try {
      const body = {
        topic_override: topicTitle.trim() === detail.title ? null : topicTitle.trim(),
        urls: Array.from(selectedUrls),
      };
      const resp = await request<{ article_id: string }>(
        `/v2/discovery/topics/${topicId}/write_article`,
        { method: "POST", body: JSON.stringify(body), headers: { "content-type": "application/json" } },
      );
      if (mounted.current) onSubmitted(resp.article_id);
    } catch (err) {
      console.error("WriteFromTopicDialog: submit failed", err);
      if (mounted.current) setSubmitting(false);
    }
  }

  // ESC closes the dialog.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !submitting) onCancel();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel, submitting]);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(28, 25, 23, 0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
        padding: 16,
      }}
      onClick={onCancel}
    >
      <div
        style={{
          background: "var(--white)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          width: "100%",
          maxWidth: 720,
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <header
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <h3 style={{ margin: 0, fontSize: 16, color: "var(--text)" }}>
            {t.discovery.dialog.title}
          </h3>
          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            style={{
              background: "none",
              border: 0,
              color: "var(--muted)",
              fontSize: 22,
              cursor: submitting ? "default" : "pointer",
              padding: 0,
              lineHeight: 1,
            }}
            aria-label="Close"
          >
            ×
          </button>
        </header>

        <div style={{ padding: 20, overflowY: "auto", flex: 1 }}>
          {!detail ? (
            <div style={{ color: "var(--muted)" }}>{t.discovery.topic.loading}</div>
          ) : (
            <>
              <label
                style={{
                  display: "block",
                  fontSize: 12,
                  color: "var(--muted)",
                  marginBottom: 4,
                }}
              >
                {t.discovery.dialog.topicLabel}
              </label>
              <input
                value={topicTitle}
                onChange={(e) => setTopicTitle(e.target.value)}
                disabled={submitting}
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  fontSize: 14,
                  background: "var(--white)",
                  color: "var(--text)",
                  boxSizing: "border-box",
                }}
              />
              <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 6 }}>
                💡 {t.discovery.dialog.titleHint}
              </div>

              <label
                style={{
                  display: "block",
                  fontSize: 12,
                  color: "var(--muted)",
                  marginTop: 16,
                  marginBottom: 6,
                }}
              >
                {t.discovery.dialog.sourcesLabel} ({selectedUrls.size}/{detail.items.length})
              </label>
              <div
                style={{
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  maxHeight: 320,
                  overflowY: "auto",
                }}
              >
                {detail.items.map((it, idx) => (
                  <div
                    key={it.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "10px 12px",
                      borderTop: idx === 0 ? "none" : "1px solid var(--border)",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedUrls.has(it.canonical_url)}
                      onChange={() => toggleUrl(it.canonical_url)}
                      disabled={submitting}
                      style={{ flexShrink: 0 }}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontWeight: 500,
                          fontSize: 14,
                          color: "var(--text)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {it.title}
                      </div>
                      <a
                        href={it.canonical_url}
                        target="_blank"
                        rel="noreferrer noopener"
                        style={{
                          fontSize: 11,
                          color: "var(--muted)",
                          display: "block",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          textDecoration: "none",
                        }}
                      >
                        {it.canonical_url} ↗
                      </a>
                    </div>
                    <button
                      type="button"
                      onClick={() => copyTitle(it.title)}
                      disabled={submitting}
                      title={t.discovery.dialog.copyTitle}
                      style={{
                        flexShrink: 0,
                        padding: 6,
                        background: "none",
                        border: "1px solid var(--border)",
                        borderRadius: 4,
                        color: copiedUrl === it.title ? "var(--accent)" : "var(--muted)",
                        cursor: submitting ? "default" : "pointer",
                        fontSize: 12,
                      }}
                    >
                      {copiedUrl === it.title ? "✓" : "⎘"}
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <footer
          style={{
            padding: "12px 20px",
            borderTop: "1px solid var(--border)",
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
          }}
        >
          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            style={{
              padding: "8px 14px",
              background: "var(--sidebar)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              color: "var(--text)",
              cursor: submitting ? "default" : "pointer",
              fontSize: 13,
            }}
          >
            {t.discovery.dialog.cancel}
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={submitting || !detail || selectedUrls.size === 0 || !topicTitle.trim()}
            style={{
              padding: "8px 14px",
              background: "var(--accent)",
              border: 0,
              borderRadius: "var(--radius)",
              color: "var(--white)",
              cursor: submitting ? "default" : "pointer",
              fontSize: 13,
              fontWeight: 500,
              opacity: submitting || selectedUrls.size === 0 || !topicTitle.trim() ? 0.6 : 1,
            }}
          >
            {submitting ? t.discovery.dialog.submitting : t.discovery.dialog.submit}
          </button>
        </footer>
      </div>
    </div>
  );
}
