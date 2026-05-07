import type { DiscoveryFeed } from "../types";
import { useT } from "../i18n";
import type { Translations } from "../i18n";

interface Props {
  feeds: DiscoveryFeed[];
  loading: boolean;
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

function statusOf(f: DiscoveryFeed, t: Translations): { label: string; bg: string; fg: string } {
  if (f.disabled) return { label: t.discovery.feed.disabled, bg: "var(--error-lt)", fg: "var(--error-fg)" };
  if (f.error_count >= 3) return { label: t.discovery.feed.degraded, bg: "var(--warning-lt)", fg: "var(--warning-fg)" };
  return { label: t.discovery.feed.healthy, bg: "var(--success-lt)", fg: "var(--success-fg)" };
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

export function FeedsHealth({ feeds, loading }: Props) {
  const t = useT();
  if (loading) {
    return <div style={{ padding: 24, color: "var(--muted)" }}>{t.discovery.topic.loading}</div>;
  }
  if (feeds.length === 0) {
    return (
      <div style={{ padding: 24, color: "var(--muted)" }}>
        {t.discovery.feed.emptyHint}
      </div>
    );
  }

  return (
    <div
      style={{
        padding: 24,
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))",
        gap: 16,
      }}
    >
      {feeds.map((f) => {
        const s = statusOf(f, t);
        return (
          <div
            key={f.id}
            style={{
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              padding: 16,
              background: "var(--white)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12, gap: 12 }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 600, color: "var(--text)" }}>{hostname(f.feed_url)}</div>
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--muted)",
                    fontFamily: "ui-monospace, Menlo, monospace",
                    wordBreak: "break-all",
                  }}
                >
                  {f.feed_url}
                </div>
              </div>
              <span
                style={{
                  color: s.fg,
                  background: s.bg,
                  fontSize: 12,
                  padding: "2px 8px",
                  borderRadius: 999,
                  flexShrink: 0,
                  alignSelf: "flex-start",
                  whiteSpace: "nowrap",
                }}
              >
                {s.label}
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
                <div style={{ fontSize: 11, color: "var(--muted)" }}>{t.discovery.feed.lastFetched}</div>
                <div style={{ fontWeight: 500, color: "var(--text)" }}>{relTime(f.last_fetched_at, t)}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--muted)" }}>{t.discovery.feed.errors}</div>
                <div
                  style={{
                    fontWeight: 500,
                    color: f.error_count > 0 ? "var(--warning-fg)" : "var(--success-fg)",
                  }}
                >
                  {f.error_count}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--muted)" }}>{t.discovery.feed.items24h}</div>
                <div style={{ fontWeight: 500, color: "var(--text)" }}>{f.items_24h_count}</div>
              </div>
            </div>
            {f.last_error && (
              <div
                style={{
                  fontSize: 12,
                  color: "var(--error-fg)",
                  marginTop: 8,
                  wordBreak: "break-word",
                }}
                title={f.last_error}
              >
                {t.discovery.feed.lastError}: {f.last_error.slice(0, 120)}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
