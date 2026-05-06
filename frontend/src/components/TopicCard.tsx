import { useEffect, useRef, useState } from "react";
import type { DiscoveryTopicSummary, DiscoveryItem } from "../types";
import { useDiscoveryTopicDetail } from "../lib/useDiscoveryTopicDetail";
import { useT } from "../i18n";

interface Props {
  topic: DiscoveryTopicSummary;
  onWrite: (topicId: string) => void;
  onSelect?: (topicId: string) => void;
}

export function TopicCard({ topic, onWrite, onSelect }: Props) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<DiscoveryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { load } = useDiscoveryTopicDetail();

  // Guard against state updates after unmount when the user changes filters
  // mid-fetch — `load` is async and the component can disappear before it
  // resolves.
  const mountedRef = useRef(true);
  useEffect(() => () => { mountedRef.current = false; }, []);

  async function toggle(e: React.MouseEvent) {
    e.stopPropagation();
    const next = !open;
    setOpen(next);
    if (next && items === null && !error) {
      try {
        const detail = await load(topic.id);
        if (mountedRef.current) setItems(detail.items);
      } catch (err) {
        if (mountedRef.current) setError(err instanceof Error ? err.message : String(err));
      }
    }
  }

  function handleWrite(e: React.MouseEvent) {
    e.stopPropagation();
    onWrite(topic.id);
  }

  function handleBodyClick() {
    onSelect?.(topic.id);
  }

  const isResurfaced = topic.status === "resurfaced";
  const isConsumed = topic.status === "consumed";

  const chipBase: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    padding: "2px 8px",
    borderRadius: 999,
    fontSize: 11,
    fontWeight: 500,
  };

  return (
    <div
      style={{
        padding: "16px 24px",
        borderBottom: "1px solid var(--border)",
        background: "var(--white)",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        <button
          type="button"
          onClick={toggle}
          aria-label={t.discovery.topic.toggleSources}
          aria-expanded={open}
          style={{
            background: "none",
            border: 0,
            cursor: "pointer",
            color: "var(--muted)",
            marginTop: 2,
            fontSize: 14,
            padding: 4,
          }}
        >
          {open ? "▾" : "▸"}
        </button>
        <div
          style={{ flex: 1, minWidth: 0, cursor: onSelect ? "pointer" : "default" }}
          onClick={handleBodyClick}
        >
          <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 4, flexWrap: "wrap" }}>
            {isResurfaced && (
              <span style={{ ...chipBase, background: "#fee2e2", color: "#b91c1c" }}>
                {t.discovery.hub.resurfaced}
              </span>
            )}
            {isConsumed && (
              <span style={{ ...chipBase, background: "#dcfce7", color: "#166534" }}>
                {t.discovery.hub.written}
              </span>
            )}
            {topic.categories.map((c) => (
              <span key={c} style={{ ...chipBase, background: "var(--accent-lt)", color: "var(--accent)" }}>
                {c}
              </span>
            ))}
          </div>
          <h4 style={{
            fontWeight: 600,
            margin: 0,
            fontSize: 15,
            color: "var(--text)",
            textDecoration: isConsumed ? "line-through" : undefined,
          }}>
            {topic.title}
          </h4>
          {topic.blurb && (
            <p
              style={{
                color: "var(--muted)",
                fontSize: 14,
                margin: "4px 0 0",
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
                lineHeight: 1.4,
              }}
            >
              {topic.blurb}
            </p>
          )}
          <div style={{ display: "flex", gap: 16, fontSize: 12, color: "var(--muted)", marginTop: 8 }}>
            <span>⏱️ {new Date(topic.last_activity_at).toLocaleString()}</span>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, flexShrink: 0 }}>
          {isConsumed ? (
            <button
              type="button"
              disabled
              style={{
                padding: "6px 12px",
                background: "var(--sidebar)",
                color: "var(--muted)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius)",
                fontSize: 13,
                cursor: "default",
              }}
            >
              {t.discovery.topic.openArticle}
            </button>
          ) : (
            <button
              type="button"
              onClick={handleWrite}
              style={{
                padding: "6px 12px",
                background: "var(--accent)",
                color: "var(--white)",
                border: 0,
                borderRadius: "var(--radius)",
                cursor: "pointer",
                fontWeight: 500,
                fontSize: 13,
              }}
            >
              {t.discovery.topic.write}
            </button>
          )}
        </div>
      </div>

      {open && (
        <div
          style={{
            marginLeft: 28,
            marginTop: 12,
            paddingLeft: 16,
            borderLeft: "2px solid var(--border)",
          }}
        >
          <div style={{ fontSize: 11, textTransform: "uppercase", color: "var(--muted)", marginBottom: 6, letterSpacing: "0.04em" }}>
            {t.discovery.topic.sources}
          </div>
          {error ? (
            <div style={{ color: "#b91c1c", fontSize: 13 }}>{t.discovery.topic.error}: {error}</div>
          ) : items === null ? (
            <div style={{ color: "var(--muted)", fontSize: 13 }}>{t.discovery.topic.loading}</div>
          ) : items.length === 0 ? (
            <div style={{ color: "var(--muted)", fontSize: 13 }}>{t.discovery.item.uncategorized}</div>
          ) : (
            items.map((it) => (
              <a
                key={it.id}
                href={it.canonical_url}
                target="_blank"
                rel="noreferrer noopener"
                onClick={(e) => e.stopPropagation()}
                style={{
                  display: "block",
                  padding: "6px 0",
                  textDecoration: "none",
                  color: "var(--text)",
                }}
              >
                <div style={{ fontSize: 14 }}>
                  {it.title} <span style={{ color: "var(--muted)" }}>↗</span>
                </div>
                <div
                  style={{
                    fontSize: 12,
                    color: "var(--muted)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {it.canonical_url}
                </div>
              </a>
            ))
          )}
        </div>
      )}
    </div>
  );
}
