import { useState } from "react";
import type { DiscoveryTopicSummary, DiscoveryItem, StreamSource } from "../types";
import { useDiscoveryTopicDetail } from "../lib/useDiscoveryTopicDetail";
import { useT } from "../i18n";
import { Button } from "./ui/Button";
import { safeHref } from "../lib/safeHref";
import { StreamSourceModal } from "./StreamSourceModal";

function formatWindow(w: { start_at: string; end_at: string }): string {
  const start = new Date(w.start_at);
  const end = new Date(w.end_at);
  const day = start.toLocaleDateString("pl-PL", { day: "numeric", month: "short" });
  const t1 = start.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
  const t2 = end.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
  return `${day}, ${t1}–${t2}`;
}

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
  const [streamSources, setStreamSources] = useState<StreamSource[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [modalStreamTopicId, setModalStreamTopicId] = useState<string | null>(null);
  const { load } = useDiscoveryTopicDetail();

  async function toggle(e: React.MouseEvent) {
    e.stopPropagation();
    const next = !open;
    setOpen(next);
    if (next && items === null && !error) {
      try {
        const detail = await load(topic.id);
        setItems(detail.items);
        setStreamSources(detail.stream_sources ?? []);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
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
              background: "var(--canvas-bg)",
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
              {topic.item_count + topic.stream_source_count} {t.discovery.hub.sourcesCount}
              {topic.stream_source_count > 0 && (
                <span style={{ color: "var(--accent)", fontWeight: 500, marginLeft: 4 }}>
                  · 📡 {topic.stream_source_count}
                </span>
              )}
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
              {topic.item_count + topic.stream_source_count} {t.discovery.topic.itemsShort}
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
          ) : (
            <>
              {streamSources.map((src) => (
                <button
                  key={src.id}
                  type="button"
                  onClick={(e) => { e.stopPropagation(); setModalStreamTopicId(src.id); }}
                  style={{
                    display: "flex", flexDirection: "column", gap: 4,
                    width: "100%", textAlign: "left",
                    padding: "6px 8px", marginBottom: 2,
                    border: "1px solid var(--card-border)", borderRadius: "var(--radius)",
                    background: "var(--card-bg)", cursor: "pointer",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <span style={{ fontSize: 10, fontWeight: 600, color: "var(--accent)", background: "var(--accent-lt)", borderRadius: 4, padding: "1px 6px", flexShrink: 0 }}>
                      📡 {src.subscription_name}
                    </span>
                    <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text)" }}>{src.title}</span>
                  </div>
                  {src.windows.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
                      {src.windows.map((w, i) => (
                        <span key={i} style={{ fontSize: 10, color: "var(--ink-subtle)", background: "var(--card-border)", borderRadius: 3, padding: "1px 5px", whiteSpace: "nowrap" }}>
                          {formatWindow(w)}
                        </span>
                      ))}
                    </div>
                  )}
                </button>
              ))}
              {items.length === 0 && streamSources.length === 0 ? (
                <div style={{ color: "var(--muted)", fontSize: 13 }}>{t.discovery.item.uncategorized}</div>
              ) : (
                items.map((it) => (
                  <a
                    key={it.id}
                    href={safeHref(it.canonical_url)}
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
                          background: "var(--canvas-bg)",
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
            </>
          )}
        </div>
      )}
      {modalStreamTopicId && (
        <StreamSourceModal
          streamTopicId={modalStreamTopicId}
          onClose={() => setModalStreamTopicId(null)}
        />
      )}
    </div>
  );
}
