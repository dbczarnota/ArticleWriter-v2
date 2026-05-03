import type { ArticleListItem } from "../types";

const STATUS_DOT: Record<string, string> = {
  done: "#22c55e",
  running: "#f59e0b",
  failed: "#ef4444",
  insufficient_sources: "#f97316",
};

interface SidebarProps {
  articles: ArticleListItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}

export function Sidebar({ articles, selectedId, onSelect, onNew }: SidebarProps) {
  return (
    <aside style={{
      width: "var(--sidebar-width)",
      background: "var(--sidebar)",
      borderRight: "1px solid var(--border)",
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
    }}>
      <div style={{
        padding: "12px 12px 8px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        borderBottom: "1px solid var(--border)",
      }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: ".05em" }}>
          Artykuły
        </span>
        <button
          onClick={onNew}
          style={{
            background: "var(--accent)",
            color: "var(--white)",
            border: "none",
            borderRadius: "var(--radius)",
            padding: "4px 10px",
            fontSize: 12,
            fontWeight: 500,
          }}
        >
          + Nowy
        </button>
      </div>
      <div style={{ overflowY: "auto", flex: 1 }}>
        {articles.length === 0 && (
          <p style={{ padding: 16, color: "var(--muted)", fontSize: 13 }}>Brak artykułów</p>
        )}
        {articles.map((a) => (
          <button
            key={a.id}
            onClick={() => onSelect(a.id)}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 10,
              width: "100%",
              padding: "10px 12px",
              background: a.id === selectedId ? "var(--accent-lt)" : "transparent",
              borderLeft: a.id === selectedId ? "3px solid var(--accent)" : "3px solid transparent",
              border: "none",
              borderBottom: "1px solid var(--border)",
              textAlign: "left",
              cursor: "pointer",
            }}
          >
            <span style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: STATUS_DOT[a.status] ?? "#94a3b8",
              flexShrink: 0,
              marginTop: 5,
            }} />
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {a.topic}
              </div>
              <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
                {a.created_at ? new Date(a.created_at).toLocaleDateString("pl") : "—"}
              </div>
            </div>
          </button>
        ))}
      </div>
    </aside>
  );
}
