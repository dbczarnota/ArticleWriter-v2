import { useState } from "react";
import type { DiscoveryFeed, StreamSubscription } from "../types";
import { useT } from "../i18n";

export interface DiscoveryFiltersValue {
  feedId: string | null;
  subscriptionId: string | null;
  categories: string[];
  statuses: string[];
}

type ActiveView = "topics" | "items" | "feeds" | "streamy" | "tematy-streamow";

interface Props {
  feeds: DiscoveryFeed[];
  subscriptions: StreamSubscription[];
  availableCategories: { name: string; count?: number }[];
  value: DiscoveryFiltersValue;
  onChange: (next: DiscoveryFiltersValue) => void;
  activeView: ActiveView;
}

export function DiscoveryFiltersSidebar({ feeds, subscriptions, availableCategories, value, onChange, activeView }: Props) {
  const t = useT();
  const [feedsOpen, setFeedsOpen] = useState(true);
  const [subsOpen, setSubsOpen] = useState(true);
  const [catsOpen, setCatsOpen] = useState(true);
  const [statusOpen, setStatusOpen] = useState(true);

  function setFeed(id: string | null) { onChange({ ...value, feedId: id }); }
  function setSubscription(id: string | null) { onChange({ ...value, subscriptionId: id }); }
  function toggleCategory(name: string) {
    const has = value.categories.includes(name);
    onChange({ ...value, categories: has ? value.categories.filter((c) => c !== name) : [...value.categories, name] });
  }
  function toggleStatus(status: string) {
    const has = value.statuses.includes(status);
    onChange({ ...value, statuses: has ? value.statuses.filter((s) => s !== status) : [...value.statuses, status] });
  }

  function hostname(url: string): string {
    try { return new URL(url).hostname; } catch { return url; }
  }

  const showFeeds = activeView !== "tematy-streamow";
  const showSubscriptions = (activeView === "topics" || activeView === "tematy-streamow") && subscriptions.length > 0;
  const showStatuses = activeView === "topics" || activeView === "items";

  const sectionLabel: React.CSSProperties = {
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: ".12em",
    textTransform: "uppercase",
    color: "var(--accent)",
    display: "flex",
    alignItems: "center",
    gap: 7,
    padding: "4px 0 8px",
    borderBottom: "1px solid var(--chrome-border)",
    cursor: "pointer",
    background: "none",
    border: "none",
    borderBottomWidth: 1,
    borderBottomStyle: "solid",
    borderBottomColor: "var(--chrome-border)",
    width: "100%",
    textAlign: "left",
    marginBottom: 4,
  };

  const dot: React.CSSProperties = {
    width: 5,
    height: 5,
    borderRadius: "50%",
    background: "currentColor",
    flexShrink: 0,
    display: "inline-block",
  };

  const chevron = (open: boolean): React.CSSProperties => ({
    marginLeft: "auto",
    fontSize: 12,
    transition: "transform .15s",
    transform: open ? "rotate(0deg)" : "rotate(-90deg)",
    display: "inline-block",
  });

  const filterBtn: React.CSSProperties = {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    width: "100%",
    padding: "5px 8px",
    background: "transparent",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
    color: "var(--chrome-muted)",
    fontSize: 13,
    textAlign: "left",
    transition: "background .12s, color .12s",
  };

  const filterBtnActive: React.CSSProperties = {
    ...filterBtn,
    background: "rgba(234,88,12,.12)",
    color: "var(--accent)",
    fontWeight: 600,
  };

  return (
    <aside
      className="chrome-scroll"
      style={{
        width: 240,
        borderRight: "1px solid var(--chrome-border)",
        padding: 12,
        background: "var(--chrome-bg2)",
        color: "var(--chrome-ink)",
        overflowY: "auto",
        flexShrink: 0,
      }}
    >
      {/* FEEDS section */}
      {showFeeds && (
        <div style={{ marginBottom: 14 }}>
          <button type="button" onClick={() => setFeedsOpen(v => !v)} style={sectionLabel}>
            <span style={dot} />
            <span style={{ flex: 1 }}>{t.discovery.filters.feeds}</span>
            <span style={chevron(feedsOpen)}>▾</span>
          </button>
          {feedsOpen && (
            <div>
              <button type="button" onClick={() => setFeed(null)} style={value.feedId === null ? filterBtnActive : filterBtn}>
                <span>{t.discovery.filters.all}</span>
              </button>
              {feeds.map((f) => (
                <button
                  type="button"
                  key={f.id}
                  onClick={() => setFeed(f.id)}
                  style={value.feedId === f.id ? filterBtnActive : filterBtn}
                >
                  <span>{hostname(f.feed_url)}</span>
                  <span style={{ color: "var(--chrome-faint)", fontSize: 11 }}>{f.items_24h_count}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* SUBSCRIPTIONS section */}
      {showSubscriptions && (
        <div style={{ marginBottom: 14 }}>
          <button type="button" onClick={() => setSubsOpen(v => !v)} style={sectionLabel}>
            <span style={dot} />
            <span style={{ flex: 1 }}>{t.discovery.filters.streams}</span>
            <span style={chevron(subsOpen)}>▾</span>
          </button>
          {subsOpen && (
            <div>
              <button type="button" onClick={() => setSubscription(null)} style={value.subscriptionId === null ? filterBtnActive : filterBtn}>
                <span>{t.discovery.filters.all}</span>
              </button>
              {subscriptions.map((s) => (
                <button
                  type="button"
                  key={s.id}
                  onClick={() => setSubscription(s.id)}
                  style={value.subscriptionId === s.id ? filterBtnActive : filterBtn}
                >
                  <span>{s.name}</span>
                  <span style={{
                    width: 8, height: 8, borderRadius: "50%",
                    background: s.status === "active" ? "var(--success)" : "var(--chrome-faint)",
                    flexShrink: 0,
                    display: "inline-block",
                  }} />
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* CATEGORIES section */}
      <div style={{ marginBottom: 14 }}>
        <button type="button" onClick={() => setCatsOpen(v => !v)} style={sectionLabel}>
          <span style={dot} />
          <span style={{ flex: 1 }}>{t.discovery.filters.categories}</span>
          <span style={chevron(catsOpen)}>▾</span>
        </button>
        {catsOpen && (
          <div>
            {availableCategories.length === 0 && (
              <div style={{ color: "var(--chrome-faint)", fontSize: 12, padding: "4px 8px" }}>
                {t.discovery.filters.emptyCategories}
              </div>
            )}
            {availableCategories.map((c) => (
              <label key={c.name} style={{ display: "flex", justifyContent: "space-between", gap: 8, padding: "4px 8px", fontSize: 13, cursor: "pointer", color: "var(--chrome-muted)" }}>
                <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input type="checkbox" checked={value.categories.includes(c.name)} onChange={() => toggleCategory(c.name)} style={{ accentColor: "var(--accent)" }} />
                  {c.name}
                </span>
                {c.count !== undefined && <span style={{ color: "var(--chrome-faint)", fontSize: 11 }}>{c.count}</span>}
              </label>
            ))}
          </div>
        )}
      </div>

      {/* STATUS section */}
      {showStatuses && (
        <div>
          <button type="button" onClick={() => setStatusOpen(v => !v)} style={sectionLabel}>
            <span style={dot} />
            <span style={{ flex: 1 }}>{t.discovery.filters.status}</span>
            <span style={chevron(statusOpen)}>▾</span>
          </button>
          {statusOpen && (
            <div>
              {[
                { id: "open", label: t.discovery.status.open },
                { id: "resurfaced", label: t.discovery.status.resurfaced },
                { id: "consumed", label: t.discovery.status.consumed },
                { id: "dismissed", label: t.discovery.status.dismissed },
              ].map((s) => (
                <label key={s.id} style={{ display: "flex", gap: 8, padding: "4px 8px", fontSize: 13, cursor: "pointer", color: "var(--chrome-muted)" }}>
                  <input type="checkbox" checked={value.statuses.includes(s.id)} onChange={() => toggleStatus(s.id)} style={{ accentColor: "var(--accent)" }} />
                  {s.label}
                </label>
              ))}
            </div>
          )}
        </div>
      )}
    </aside>
  );
}
