import { useEffect, useState } from "react";
import { useApi } from "../lib/useApi";
import type { DiscoveryItem, DiscoveryTopicDetail } from "../types";
import { useT } from "../i18n";
import { Button } from "./ui/Button";
import { StatusMessage } from "./ui/StatusMessage";

interface Props {
  topicId: string;
  onBack: () => void;
  onWrite: (topicId: string) => void;
}

function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return "?";
  }
}

export function TopicDetail({ topicId, onBack, onWrite }: Props) {
  const t = useT();
  const { request } = useApi();
  const [detail, setDetail] = useState<DiscoveryTopicDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setError(null);
    request<DiscoveryTopicDetail>(`/v2/discovery/topics/${topicId}`)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [request, topicId]);

  if (error) {
    return (
      <div style={{ padding: 24, color: "var(--error-fg)" }}>
        {t.discovery.topic.error}: {error}
      </div>
    );
  }
  if (!detail) {
    return <StatusMessage kind="loading">{t.discovery.topic.loading}</StatusMessage>;
  }

  // Group items by hostname.
  const groups = new Map<string, DiscoveryItem[]>();
  for (const it of detail.items) {
    const host = hostnameOf(it.canonical_url);
    const arr = groups.get(host);
    if (arr) arr.push(it);
    else groups.set(host, [it]);
  }

  const isResurfaced = detail.status === "resurfaced";
  const isConsumed = detail.status === "consumed";

  const chipBase: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    padding: "2px 8px",
    borderRadius: 999,
    fontSize: 11,
    fontWeight: 500,
  };

  return (
    <div>
      <div
        style={{
          padding: "12px 24px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          gap: 12,
          alignItems: "center",
          background: "var(--white)",
        }}
      >
        <button
          type="button"
          onClick={onBack}
          style={{
            background: "none",
            border: 0,
            color: "var(--muted)",
            cursor: "pointer",
            padding: 0,
            fontSize: 14,
          }}
        >
          {t.discovery.topic.backToTopics}
        </button>
        <span style={{ color: "var(--muted)" }}>/</span>
        <span style={{ color: "var(--text)", fontWeight: 500 }}>{detail.title}</span>
      </div>
      <div
        style={{
          padding: 24,
          display: "grid",
          gridTemplateColumns: "1fr 320px",
          gap: 24,
        }}
      >
        <section style={{ minWidth: 0 }}>
          <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
            {detail.topic_image_url && (
              <img
                src={detail.topic_image_url}
                alt=""
                loading="lazy"
                referrerPolicy="no-referrer"
                onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
                style={{
                  width: 160,
                  height: 110,
                  objectFit: "cover",
                  borderRadius: "var(--radius)",
                  flexShrink: 0,
                  background: "var(--sidebar)",
                }}
              />
            )}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", gap: 6, marginBottom: 8, flexWrap: "wrap" }}>
                {isResurfaced && (
                  <span style={{ ...chipBase, background: "var(--error-lt)", color: "var(--error-fg)" }}>
                    {t.discovery.hub.resurfaced}
                  </span>
                )}
                {isConsumed && (
                  <span style={{ ...chipBase, background: "var(--success-lt)", color: "var(--success-fg)" }}>
                    {t.discovery.hub.written}
                  </span>
                )}
                {detail.categories.map((c) => (
                  <span
                    key={c}
                    style={{ ...chipBase, background: "var(--accent-lt)", color: "var(--accent)" }}
                  >
                    {c}
                  </span>
                ))}
              </div>
              <h2 style={{ margin: "0 0 12px", color: "var(--text)" }}>{detail.title}</h2>
              {detail.blurb && (
                <p style={{ color: "var(--muted)", lineHeight: 1.6, marginTop: 0 }}>
                  {detail.blurb}
                </p>
              )}
            </div>
          </div>

          <h3 style={{ marginTop: 24, color: "var(--text)", fontSize: 15 }}>
            {t.discovery.topic.sources} ({detail.items.length})
          </h3>
          {Array.from(groups.entries()).map(([host, group]) => (
            <div
              key={host}
              style={{
                border: "1px solid var(--border)",
                borderRadius: "var(--radius)",
                marginBottom: 12,
                overflow: "hidden",
                background: "var(--white)",
              }}
            >
              <div
                style={{
                  background: "var(--sidebar)",
                  padding: "8px 16px",
                  fontSize: 13,
                  borderBottom: "1px solid var(--border)",
                }}
              >
                <strong style={{ color: "var(--text)" }}>{host}</strong>{" "}
                <span style={{ color: "var(--muted)" }}>· {group.length} {t.discovery.topic.itemsShort}</span>
              </div>
              {group.map((it, idx) => (
                <div
                  key={it.id}
                  style={{
                    padding: "12px 16px",
                    borderTop: idx === 0 ? "none" : "1px solid var(--border)",
                    display: "flex",
                    gap: 12,
                    alignItems: "flex-start",
                  }}
                >
                  {it.image_url && (
                    <img
                      src={it.image_url}
                      alt=""
                      loading="lazy"
                      referrerPolicy="no-referrer"
                      onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
                      style={{
                        width: 64,
                        height: 64,
                        objectFit: "cover",
                        borderRadius: 4,
                        flexShrink: 0,
                        background: "var(--sidebar)",
                      }}
                    />
                  )}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <a
                      href={it.canonical_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      style={{
                        fontWeight: 500,
                        color: "var(--text)",
                        textDecoration: "none",
                        fontSize: 14,
                      }}
                    >
                      {it.title} <span style={{ color: "var(--muted)" }}>↗</span>
                    </a>
                    <div
                      style={{
                        fontSize: 12,
                        color: "var(--muted)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        marginTop: 2,
                      }}
                    >
                      {it.canonical_url}
                    </div>
                  </div>
                  {it.fetched_at && (
                    <div
                      style={{
                        fontSize: 11,
                        color: "var(--muted)",
                        flexShrink: 0,
                        whiteSpace: "nowrap",
                      }}
                      title={new Date(it.fetched_at).toLocaleString()}
                    >
                      {new Date(it.fetched_at).toLocaleString()}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))}
        </section>

        <aside>
          {isConsumed ? (
            <button
              type="button"
              disabled
              style={{
                width: "100%",
                padding: "10px 16px",
                background: "var(--sidebar)",
                color: "var(--muted)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius)",
                cursor: "default",
                fontWeight: 500,
                marginBottom: 16,
                fontSize: 14,
              }}
            >
              {t.discovery.topic.openArticle}
            </button>
          ) : (
            <Button
              variant="primary"
              size="md"
              style={{ width: "100%", marginBottom: 16 }}
              onClick={() => onWrite(topicId)}
            >
              {t.discovery.topic.writeArticle}
            </Button>
          )}
          <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.8 }}>
            <div>
              {t.discovery.topic.firstSeen}:{" "}
              {detail.first_seen_at ? new Date(detail.first_seen_at).toLocaleString() : "—"}
            </div>
            <div>
              {t.discovery.topic.lastActivity}: {new Date(detail.last_activity_at).toLocaleString()}
            </div>
            <div>{t.discovery.topic.statusLabel}: {detail.status}</div>
            <div>{t.discovery.topic.itemsCount}: {detail.items.length}</div>
          </div>
        </aside>
      </div>
    </div>
  );
}
