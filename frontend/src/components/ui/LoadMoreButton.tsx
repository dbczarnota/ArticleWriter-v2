interface Props {
  hasMore: boolean;
  loading: boolean;
  onClick: () => void;
}

export function LoadMoreButton({ hasMore, loading, onClick }: Props) {
  if (!hasMore && !loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: "16px 0", color: "var(--muted)", fontSize: 12 }}>
        — koniec listy —
      </div>
    );
  }
  return (
    <div style={{ display: "flex", justifyContent: "center", padding: "16px 0" }}>
      <button
        type="button"
        onClick={onClick}
        disabled={loading || !hasMore}
        style={{
          padding: "8px 24px",
          background: "var(--white)",
          color: "var(--accent)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          fontSize: 13,
          fontWeight: 500,
          cursor: loading ? "default" : "pointer",
          opacity: loading ? 0.6 : 1,
        }}
      >
        {loading ? "Ładowanie…" : "Załaduj więcej"}
      </button>
    </div>
  );
}
