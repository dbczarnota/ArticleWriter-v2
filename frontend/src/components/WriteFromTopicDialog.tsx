import { useEffect, useRef, useState } from "react";
import type { DiscoveryTopicDetail } from "../types";
import { useApi } from "../lib/useApi";
import { useFocusTrap } from "../lib/useFocusTrap";
import { useT } from "../i18n";
import { Button } from "./ui/Button";
import { safeHref } from "../lib/safeHref";

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
  const [instructions, setInstructions] = useState("");
  const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set());
  // URLs the editor pasted in addition to the discovered sources.
  // Stored separately so the discovered list keeps its full metadata
  // (title + copy button) while customs render as bare URLs with a
  // remove button.
  const [customUrls, setCustomUrls] = useState<string[]>([]);
  const [customUrlInput, setCustomUrlInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null);
  const mounted = useRef(true);
  const dialogRef = useFocusTrap<HTMLDivElement>(true);

  useEffect(() => () => { mounted.current = false; }, []);

  useEffect(() => {
    let cancelled = false;
    void request<DiscoveryTopicDetail>(`/v2/discovery/topics/${topicId}`).then((d) => {
      if (cancelled) return;
      setDetail(d);
      setTopicTitle(d.title);
      // Default instructions = topic blurb (the matcher signal). Editor
      // can override or wipe it before generating.
      setInstructions(d.blurb || "");
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

  function addCustomUrl() {
    const raw = customUrlInput.trim();
    if (!raw) return;
    // Accept anything that parses as an http(s) URL — same lenience as the
    // regular write-article form. Bad URLs would surface in the pipeline.
    let normalized: string;
    try {
      const parsed = new URL(raw);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return;
      normalized = parsed.toString();
    } catch {
      return;
    }
    if (
      customUrls.includes(normalized) ||
      detail?.items.some((it) => it.canonical_url === normalized)
    ) {
      setCustomUrlInput("");
      return;
    }
    setCustomUrls((prev) => [...prev, normalized]);
    setSelectedUrls((prev) => new Set(prev).add(normalized));
    setCustomUrlInput("");
  }

  function removeCustomUrl(url: string) {
    setCustomUrls((prev) => prev.filter((u) => u !== url));
    setSelectedUrls((prev) => {
      const next = new Set(prev);
      next.delete(url);
      return next;
    });
  }

  async function submit() {
    if (!detail) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const body = {
        topic_override: topicTitle.trim() === detail.title ? null : topicTitle.trim(),
        additional_instructions: instructions.trim() || null,
        urls: Array.from(selectedUrls),
      };
      // useApi.request already sets Content-Type: application/json; passing
      // it again here would just duplicate the header. Body is JSON.stringified
      // here because fetch() doesn't auto-serialize a plain object.
      const resp = await request<{ article_id: string }>(
        `/v2/discovery/topics/${topicId}/write_article`,
        { method: "POST", body: JSON.stringify(body) },
      );
      if (!mounted.current) return;
      if (!resp || !resp.article_id) {
        console.error("WriteFromTopicDialog: empty response", resp);
        setSubmitError("Empty server response");
        setSubmitting(false);
        return;
      }
      onSubmitted(resp.article_id);
    } catch (err) {
      console.error("WriteFromTopicDialog: submit failed", err);
      if (mounted.current) {
        setSubmitError(err instanceof Error ? err.message : String(err));
        setSubmitting(false);
      }
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
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="write-dialog-title"
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
          <h3 id="write-dialog-title" style={{ margin: 0, fontSize: 16, color: "var(--text)" }}>
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

              <label
                htmlFor="write-dialog-instructions"
                style={{
                  display: "block",
                  fontSize: 12,
                  color: "var(--muted)",
                  marginTop: 16,
                  marginBottom: 4,
                }}
              >
                {t.discovery.dialog.instructionsLabel}
              </label>
              <textarea
                id="write-dialog-instructions"
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                disabled={submitting}
                rows={3}
                placeholder={t.discovery.dialog.instructionsPlaceholder}
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  fontSize: 13,
                  lineHeight: 1.4,
                  background: "var(--white)",
                  color: "var(--text)",
                  boxSizing: "border-box",
                  resize: "vertical",
                  fontFamily: "inherit",
                }}
              />

              <label
                style={{
                  display: "block",
                  fontSize: 12,
                  color: "var(--muted)",
                  marginTop: 16,
                  marginBottom: 6,
                }}
              >
                {t.discovery.dialog.sourcesLabel} ({selectedUrls.size}/{detail.items.length + customUrls.length})
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
                        href={safeHref(it.canonical_url)}
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
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        padding: "3px 4px",
                        background: "transparent",
                        color: copiedUrl === it.title ? "var(--success)" : "var(--muted)",
                        border: "none",
                        borderRadius: "var(--radius)",
                        cursor: submitting ? "default" : "pointer",
                        lineHeight: 1,
                        transition: "color 0.15s",
                      }}
                    >
                      {copiedUrl === it.title ? (
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      ) : (
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                        </svg>
                      )}
                    </button>
                  </div>
                ))}
                {customUrls.map((url) => (
                  <div
                    key={url}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "10px 12px",
                      borderTop: "1px solid var(--border)",
                      background: "var(--accent-lt)",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedUrls.has(url)}
                      onChange={() => toggleUrl(url)}
                      disabled={submitting}
                      style={{ flexShrink: 0 }}
                    />
                    <a
                      href={safeHref(url)}
                      target="_blank"
                      rel="noreferrer noopener"
                      style={{
                        flex: 1,
                        minWidth: 0,
                        fontSize: 13,
                        color: "var(--text)",
                        textDecoration: "none",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {url} ↗
                    </a>
                    <button
                      type="button"
                      onClick={() => removeCustomUrl(url)}
                      disabled={submitting}
                      title={t.discovery.dialog.removeUrl}
                      style={{
                        flexShrink: 0,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        padding: 6,
                        background: "var(--white)",
                        color: "var(--muted)",
                        border: "1px solid var(--border)",
                        borderRadius: "var(--radius)",
                        cursor: submitting ? "default" : "pointer",
                      }}
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18" />
                        <line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>

              <div
                style={{
                  display: "flex",
                  gap: 8,
                  marginTop: 8,
                }}
              >
                <input
                  type="url"
                  inputMode="url"
                  value={customUrlInput}
                  onChange={(e) => setCustomUrlInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addCustomUrl();
                    }
                  }}
                  disabled={submitting}
                  placeholder={t.discovery.dialog.addUrlPlaceholder}
                  style={{
                    flex: 1,
                    padding: "8px 10px",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius)",
                    fontSize: 13,
                    background: "var(--white)",
                    color: "var(--text)",
                    boxSizing: "border-box",
                  }}
                />
                <Button
                  variant="outline"
                  size="md"
                  onClick={addCustomUrl}
                  disabled={submitting || !customUrlInput.trim()}
                >
                  {t.discovery.dialog.addUrl}
                </Button>
              </div>
            </>
          )}
        </div>

        {submitError && (
          <div
            style={{
              padding: "8px 20px",
              borderTop: "1px solid var(--border)",
              background: "var(--error-lt)",
              color: "var(--error-fg)",
              fontSize: 12,
              wordBreak: "break-word",
            }}
          >
            {submitError}
          </div>
        )}
        <footer
          style={{
            padding: "12px 20px",
            borderTop: "1px solid var(--border)",
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
          }}
        >
          <Button variant="ghost" size="md" onClick={onCancel} disabled={submitting}>
            {t.discovery.dialog.cancel}
          </Button>
          <Button
            variant="primary"
            size="md"
            onClick={submit}
            disabled={submitting || !detail || selectedUrls.size === 0 || !topicTitle.trim()}
          >
            {submitting ? t.discovery.dialog.submitting : t.discovery.dialog.submit}
          </Button>
        </footer>
      </div>
    </div>
  );
}
