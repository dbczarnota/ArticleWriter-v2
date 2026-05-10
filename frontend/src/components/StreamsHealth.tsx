import type { StreamSubscription } from "../types";
import { StatusMessage } from "./ui/StatusMessage";
import { useT } from "../i18n";
import type { Translations } from "../i18n";

interface Props {
  subscriptions: StreamSubscription[];
  loading: boolean;
  onDelete: (id: string) => Promise<void>;
}

function relTime(iso: string | null, t: Translations): string {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.round(ms / 60000);
  if (min < 1) return t.discovery.feed.justNow;
  if (min < 60) return `${min} ${t.discovery.feed.minAgo}`;
  const h = Math.round(min / 60);
  if (h < 24) return `${h}${t.discovery.feed.hAgo}`;
  return `${Math.round(h / 24)}${t.discovery.feed.dAgo}`;
}

function statusBadge(
  status: StreamSubscription["status"],
  t: Translations,
): { label: string; bg: string; fg: string } {
  if (status === "active")
    return { label: t.streams.subscription.live, bg: "var(--success-lt)", fg: "var(--success-fg)" };
  if (status === "paused")
    return { label: t.streams.subscription.paused, bg: "var(--warning-lt)", fg: "var(--warning-fg)" };
  return { label: t.streams.subscription.stopped, bg: "var(--error-lt)", fg: "var(--error-fg)" };
}

export function StreamsHealth({ subscriptions, loading, onDelete }: Props) {
  const t = useT();

  if (loading) return <StatusMessage kind="loading">{t.streams.topic.loading}</StatusMessage>;
  if (subscriptions.length === 0)
    return <StatusMessage kind="empty">{t.streams.subscription.noStreams}</StatusMessage>;

  return (
    <div
      style={{
        padding: 24,
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))",
        gap: 16,
      }}
    >
      {subscriptions.map((sub) => {
        const badge = statusBadge(sub.status, t);
        return (
          <div
            key={sub.id}
            style={{
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              padding: 16,
              background: "var(--white)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12, gap: 12 }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 600, color: "var(--text)" }}>{sub.name}</div>
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--muted)",
                    fontFamily: "ui-monospace, Menlo, monospace",
                    wordBreak: "break-all",
                  }}
                >
                  {sub.stream_url}
                </div>
              </div>
              <span
                style={{
                  color: badge.fg,
                  background: badge.bg,
                  fontSize: 12,
                  padding: "2px 8px",
                  borderRadius: 999,
                  flexShrink: 0,
                  alignSelf: "flex-start",
                  whiteSpace: "nowrap",
                }}
              >
                {badge.label}
              </span>
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: 12,
                fontSize: 14,
              }}
            >
              <div>
                <div style={{ fontSize: 11, color: "var(--muted)" }}>{t.streams.subscription.streamType}</div>
                <div style={{ fontWeight: 500, color: "var(--text)", textTransform: "uppercase" }}>
                  {sub.stream_type}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--muted)" }}>{t.streams.subscription.chunkDuration}</div>
                <div style={{ fontWeight: 500, color: "var(--text)" }}>{sub.chunk_duration_seconds}s</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--muted)" }}>{t.streams.subscription.lastStarted}</div>
                <div style={{ fontWeight: 500, color: "var(--text)" }}>
                  {relTime(sub.started_at, t)}
                </div>
              </div>
            </div>
            <div style={{ marginTop: 12, display: "flex", justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={() => {
                  if (window.confirm(t.streams.subscription.confirmDelete)) {
                    void onDelete(sub.id);
                  }
                }}
                style={{
                  fontSize: 12,
                  color: "var(--error-fg)",
                  background: "none",
                  border: "1px solid var(--error-fg)",
                  borderRadius: "var(--radius)",
                  padding: "3px 10px",
                  cursor: "pointer",
                }}
              >
                {t.streams.subscription.delete}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
