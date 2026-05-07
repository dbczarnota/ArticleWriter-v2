import { useEffect, useRef, useState } from "react";
import type { DiscoveryTopicSummary, DiscoveryItem } from "../types";
import { useDiscoveryTopicDetail } from "../lib/useDiscoveryTopicDetail";
import { useT } from "../i18n";
import { Button } from "./ui/Button";

// Monochrome 13×13 outline icons matching the copy-button style
// (stroke=currentColor, no fill). Kept inline so the meta row can
// stay one self-contained component.
const ICON_PROPS = {
  width: 13,
  height: 13,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};
function SourcesIcon() {
  return (
    <svg {...ICON_PROPS} aria-hidden>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <line x1="10" y1="9" x2="8" y2="9" />
    </svg>
  );
}
function CalendarIcon() {
  return (
    <svg {...ICON_PROPS} aria-hidden>
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}
function ClockIcon() {
  return (
    <svg {...ICON_PROPS} aria-hidden>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}
function GlobeIcon() {
  return (
    <svg {...ICON_PROPS} aria-hidden>
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  );
}
const metaItem: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 5,
  whiteSpace: "nowrap",
};

interface Props {
  topic: DiscoveryTopicSummary;
  onWrite: (topicId: string) => void;
  onSelect?: (topicId: string) => void;
  onDismiss?: (topicId: string) => void;
  onRestore?: (topicId: string) => void;
  pendingActionId?: string | null;
}

export function TopicCard({ topic, onWrite, onSelect, onDismiss, onRestore, pendingActionId }: Props) {
  const isPending = pendingActionId === topic.id;
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

  function handleBodyClick() {
    onSelect?.(topic.id);
  }

  const isResurfaced = topic.status === "resurfaced";
  const isConsumed = topic.status === "consumed";
  const isDismissed = topic.status === "dismissed";

  function handleDismiss(e: React.MouseEvent) {
    e.stopPropagation();
    onDismiss?.(topic.id);
  }
  function handleRestore(e: React.MouseEvent) {
    e.stopPropagation();
    onRestore?.(topic.id);
  }

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
        {topic.topic_image_url && (
          <img
            src={topic.topic_image_url}
            alt=""
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
            onClick={handleBodyClick}
            style={{
              width: 72,
              height: 72,
              objectFit: "cover",
              borderRadius: "var(--radius)",
              flexShrink: 0,
              cursor: onSelect ? "pointer" : "default",
              background: "var(--sidebar)",
            }}
          />
        )}
        <div
          style={{ flex: 1, minWidth: 0, cursor: onSelect ? "pointer" : "default" }}
          onClick={handleBodyClick}
        >
          <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 4, flexWrap: "wrap" }}>
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
          <div
            style={{
              display: "flex",
              gap: 14,
              fontSize: 12,
              color: "var(--muted)",
              marginTop: 8,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <span style={metaItem}>
              <SourcesIcon />
              {topic.item_count} {t.discovery.hub.sourcesCount}
            </span>
            {topic.first_seen_at && (
              <span style={metaItem} title={t.discovery.topic.firstSeen}>
                <CalendarIcon />
                {t.discovery.topic.firstSeenShort}: {new Date(topic.first_seen_at).toLocaleString()}
              </span>
            )}
            <span style={metaItem} title={t.discovery.topic.lastActivity}>
              <ClockIcon />
              {t.discovery.topic.lastActivityShort}: {new Date(topic.last_activity_at).toLocaleString()}
            </span>
            {topic.feed_hosts.length > 0 && (
              <span style={metaItem}>
                <GlobeIcon />
                {topic.feed_hosts.join(", ")}
              </span>
            )}
            {!isConsumed && !isDismissed && onDismiss && (
              <button
                type="button"
                onClick={handleDismiss}
                disabled={isPending}
                style={{
                  background: "none",
                  border: 0,
                  padding: 0,
                  fontSize: 12,
                  color: "var(--muted)",
                  cursor: isPending ? "default" : "pointer",
                  textDecoration: "underline",
                  textUnderlineOffset: 2,
                  opacity: isPending ? 0.5 : undefined,
                }}
                onMouseEnter={(e) => { e.currentTarget.style.color = "var(--error-fg)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = "var(--muted)"; }}
              >
                {t.discovery.topic.dismiss}
              </button>
            )}
            {isDismissed && onRestore && (
              <button
                type="button"
                onClick={handleRestore}
                disabled={isPending}
                style={{
                  background: "none",
                  border: 0,
                  padding: 0,
                  fontSize: 12,
                  color: "var(--accent)",
                  cursor: isPending ? "default" : "pointer",
                  textDecoration: "underline",
                  textUnderlineOffset: 2,
                  opacity: isPending ? 0.5 : undefined,
                }}
              >
                {t.discovery.topic.restore}
              </button>
            )}
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, flexShrink: 0, alignItems: "flex-end" }}>
          {isConsumed ? (
            <Button variant="ghost" size="sm" disabled>
              {t.discovery.topic.openArticle}
            </Button>
          ) : (
            <Button variant="primary" size="sm" onClick={(e) => { e.stopPropagation(); onWrite(topic.id); }}>
              {t.discovery.topic.write}
            </Button>
          )}
          {!isConsumed && (
            <span style={{ fontSize: 11, color: "var(--muted)" }}>
              {topic.item_count} {t.discovery.topic.itemsShort}
            </span>
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
            <div style={{ color: "var(--error-fg)", fontSize: 13 }}>{t.discovery.topic.error}: {error}</div>
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
                  display: "flex",
                  gap: 10,
                  alignItems: "center",
                  padding: "6px 0",
                  textDecoration: "none",
                  color: "var(--text)",
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
                      width: 44,
                      height: 44,
                      objectFit: "cover",
                      borderRadius: 4,
                      flexShrink: 0,
                      background: "var(--sidebar)",
                    }}
                  />
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
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
                </div>
              </a>
            ))
          )}
        </div>
      )}
    </div>
  );
}
