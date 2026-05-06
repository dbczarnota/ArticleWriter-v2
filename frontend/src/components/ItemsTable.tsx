import type { DiscoveryItem } from "../types";
import { useT } from "../i18n";

interface Props {
  items: DiscoveryItem[];
  loading: boolean;
}

export function ItemsTable({ items, loading }: Props) {
  const t = useT();
  if (loading) {
    return <div style={{ padding: 24, color: "var(--muted)" }}>{t.discovery.topic.loading}</div>;
  }
  if (items.length === 0) {
    return <div style={{ padding: 24, color: "var(--muted)" }}>{t.discovery.item.empty}</div>;
  }

  const chip: React.CSSProperties = {
    display: "inline-flex",
    background: "var(--accent-lt)",
    color: "var(--accent)",
    padding: "2px 8px",
    borderRadius: 999,
    fontSize: 11,
    marginRight: 4,
  };

  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
      <thead>
        <tr style={{
          background: "var(--sidebar)",
          color: "var(--muted)",
          fontSize: 12,
          textAlign: "left",
        }}>
          <th style={{ padding: "8px 24px", fontWeight: 500 }}>{t.discovery.item.colItem}</th>
          <th style={{ padding: 8, fontWeight: 500 }}>{t.discovery.item.colCategories}</th>
          <th style={{ padding: 8, fontWeight: 500 }}>{t.discovery.item.colSeen}</th>
        </tr>
      </thead>
      <tbody>
        {items.map((it) => (
          <tr
            key={it.id}
            style={{ borderBottom: "1px solid var(--border)", background: "var(--white)" }}
          >
            <td style={{ padding: "12px 24px" }}>
              <a
                href={it.canonical_url}
                target="_blank"
                rel="noreferrer noopener"
                style={{ fontWeight: 500, color: "var(--text)", textDecoration: "none" }}
              >
                {it.title} <span style={{ color: "var(--muted)" }}>↗</span>
              </a>
              <div style={{
                fontSize: 11,
                color: "var(--muted)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                maxWidth: 480,
              }}>
                {it.canonical_url}
              </div>
            </td>
            <td style={{ padding: 8 }}>
              {it.categories.length === 0 ? (
                <span style={{ color: "var(--muted)", fontStyle: "italic", fontSize: 12 }}>
                  {t.discovery.item.uncategorized}
                </span>
              ) : (
                it.categories.map((c) => <span key={c} style={chip}>{c}</span>)
              )}
            </td>
            <td style={{ padding: 8, color: "var(--muted)" }}>
              {it.fetched_at ? new Date(it.fetched_at).toLocaleString() : "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
