import type { DiscoveryFeed, StreamSubscription } from "../types";
import { useT } from "../i18n";

export interface DiscoveryFiltersValue {
  feedId: string | null;
  subscriptionId: string | null;
  categories: string[];
  statuses: string[];
}

interface Props {
  feeds: DiscoveryFeed[];
  subscriptions: StreamSubscription[];
  availableCategories: { name: string; count?: number }[];
  value: DiscoveryFiltersValue;
  onChange: (next: DiscoveryFiltersValue) => void;
}

export function DiscoveryFiltersSidebar({ feeds, subscriptions, availableCategories, value, onChange }: Props) {
  const t = useT();
  function setFeed(id: string | null) {
    onChange({ ...value, feedId: id });
  }
  function setSubscription(id: string | null) {
    onChange({ ...value, subscriptionId: id });
  }
  function toggleCategory(name: string) {
    const has = value.categories.includes(name);
    onChange({
      ...value,
      categories: has ? value.categories.filter((c) => c !== name) : [...value.categories, name],
    });
  }
  function toggleStatus(status: string) {
    const has = value.statuses.includes(status);
    onChange({
      ...value,
      statuses: has ? value.statuses.filter((s) => s !== status) : [...value.statuses, status],
    });
  }

  function hostname(url: string): string {
    try {
      return new URL(url).hostname;
    } catch {
      return url;
    }
  }

  const labelStyle: React.CSSProperties = {
    fontSize: 11,
    textTransform: "uppercase",
    color: "var(--muted)",
    cursor: "pointer",
    letterSpacing: "0.04em",
    padding: "4px 0",
  };

  const buttonRow: React.CSSProperties = {
    display: "flex",
    justifyContent: "space-between",
    width: "100%",
    padding: "5px 10px 5px 12px",
    background: "transparent",
    border: "none",
    borderLeft: "3px solid transparent",
    borderRadius: 0,
    cursor: "pointer",
    color: "var(--text)",
    fontSize: 13,
    textAlign: "left",
  };

  const buttonRowActive: React.CSSProperties = {
    ...buttonRow,
    borderLeft: "3px solid var(--accent)",
    color: "var(--accent)",
    fontWeight: 500,
  };

  return (
    <aside
      style={{
        width: 240,
        borderRight: "1px solid var(--border)",
        padding: 12,
        background: "var(--sidebar)",
        overflowY: "auto",
        flexShrink: 0,
      }}
    >
      <details open style={{ marginBottom: 16 }}>
        <summary style={labelStyle}>{t.discovery.filters.feeds}</summary>
        <div style={{ marginTop: 8 }}>
          <button
            type="button"
            onClick={() => setFeed(null)}
            style={value.feedId === null ? buttonRowActive : buttonRow}
          >
            <span>{t.discovery.filters.all}</span>
          </button>
          {feeds.map((f) => (
            <button
              type="button"
              key={f.id}
              onClick={() => setFeed(f.id)}
              style={value.feedId === f.id ? buttonRowActive : buttonRow}
            >
              <span>{hostname(f.feed_url)}</span>
              <span style={{ color: "var(--muted)", fontSize: 12 }}>{f.items_24h_count}</span>
            </button>
          ))}
        </div>
      </details>

      {subscriptions.length > 0 && (
        <details open style={{ marginBottom: 16 }}>
          <summary style={labelStyle}>{t.discovery.filters.streams}</summary>
          <div style={{ marginTop: 8 }}>
            <button
              type="button"
              onClick={() => setSubscription(null)}
              style={value.subscriptionId === null ? buttonRowActive : buttonRow}
            >
              <span>{t.discovery.filters.all}</span>
            </button>
            {subscriptions.map((s) => (
              <button
                type="button"
                key={s.id}
                onClick={() => setSubscription(s.id)}
                style={value.subscriptionId === s.id ? buttonRowActive : buttonRow}
              >
                <span>{s.name}</span>
                <span
                  style={{
                    fontSize: 10,
                    color: s.status === "active" ? "rgb(22,163,74)" : "var(--muted)",
                    fontWeight: 600,
                    textTransform: "uppercase",
                  }}
                >
                  {s.status === "active" ? "●" : "○"}
                </span>
              </button>
            ))}
          </div>
        </details>
      )}

      <details open style={{ marginBottom: 16 }}>
        <summary style={labelStyle}>{t.discovery.filters.categories}</summary>
        <div style={{ marginTop: 8 }}>
          {availableCategories.length === 0 && (
            <div style={{ color: "var(--muted)", fontSize: 12, padding: "4px 10px" }}>
              {t.discovery.filters.emptyCategories}
            </div>
          )}
          {availableCategories.map((c) => (
            <label
              key={c.name}
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 8,
                padding: "4px 10px",
                fontSize: 14,
                cursor: "pointer",
              }}
            >
              <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={value.categories.includes(c.name)}
                  onChange={() => toggleCategory(c.name)}
                />
                {c.name}
              </span>
              {c.count !== undefined && (
                <span style={{ color: "var(--muted)", fontSize: 12 }}>{c.count}</span>
              )}
            </label>
          ))}
        </div>
      </details>

      <details>
        <summary style={labelStyle}>{t.discovery.filters.status}</summary>
        <div style={{ marginTop: 8 }}>
          {[
            { id: "open", label: t.discovery.status.open },
            { id: "resurfaced", label: t.discovery.status.resurfaced },
            { id: "consumed", label: t.discovery.status.consumed },
            { id: "dismissed", label: t.discovery.status.dismissed },
          ].map((s) => (
            <label
              key={s.id}
              style={{
                display: "flex",
                gap: 8,
                padding: "4px 10px",
                fontSize: 14,
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={value.statuses.includes(s.id)}
                onChange={() => toggleStatus(s.id)}
              />
              {s.label}
            </label>
          ))}
        </div>
      </details>
    </aside>
  );
}
