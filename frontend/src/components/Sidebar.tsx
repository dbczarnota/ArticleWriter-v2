import { useState } from "react";
import type { ArticleListItem } from "../types";
import type { DateRange } from "../lib/useArticles";
import { useT, useLang } from "../i18n";
import { DateRangePicker } from "./DateRangePicker";

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
  currentUserId?: string;
  dateRange: DateRange;
  isFiltered: boolean;
  hasMore: boolean;
  loadingMore: boolean;
  onDateRangeChange: (next: DateRange) => void;
  onLoadMore: () => void;
}

type DoneFilter = "all" | "undone" | "done";

export function Sidebar({
  articles,
  selectedId,
  onSelect,
  onNew,
  currentUserId,
  dateRange,
  isFiltered,
  hasMore,
  loadingMore,
  onDateRangeChange,
  onLoadMore,
}: SidebarProps) {
  const t = useT();
  const { lang } = useLang();
  const [onlyMine, setOnlyMine] = useState(false);
  const [doneFilter, setDoneFilter] = useState<DoneFilter>("all");
  const [datesOpen, setDatesOpen] = useState(false);

  const visible = articles
    .filter((a) => !onlyMine || !currentUserId || a.author_user_id === currentUserId)
    .filter((a) => doneFilter === "all" ? true : doneFilter === "done" ? a.marked_done : !a.marked_done);

  const labels: Record<DoneFilter, string> = {
    all: t.sidebar.filterAll,
    undone: t.sidebar.filterUndone,
    done: t.sidebar.filterDone,
  };

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
          {t.sidebar.articles}
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
          {t.sidebar.newArticle}
        </button>
      </div>

      <div style={{ padding: "6px 12px", borderBottom: "1px solid var(--border)", display: "flex", gap: 6, flexWrap: "wrap" }}>
        {(["all", "undone", "done"] as DoneFilter[]).map((f) => {
          const active = doneFilter === f;
          return (
            <button key={f} onClick={() => setDoneFilter(f)} style={{
              background: active ? "var(--accent)" : "transparent",
              color: active ? "var(--white)" : "var(--muted)",
              border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
              borderRadius: "var(--radius)",
              padding: "3px 8px",
              fontSize: 11,
              fontWeight: 500,
              cursor: "pointer",
            }}>{labels[f]}</button>
          );
        })}
        {currentUserId && (
          <button onClick={() => setOnlyMine((v) => !v)} style={{
            background: onlyMine ? "var(--accent)" : "transparent",
            color: onlyMine ? "var(--white)" : "var(--muted)",
            border: `1px solid ${onlyMine ? "var(--accent)" : "var(--border)"}`,
            borderRadius: "var(--radius)",
            padding: "3px 8px",
            fontSize: 11,
            fontWeight: 500,
            cursor: "pointer",
          }}>{t.sidebar.filterMine}</button>
        )}
      </div>

      {/* Date range filter — opens a popover picker (DateRangePicker) with
          presets on the left and a two-month calendar on the right. */}
      <div style={{ padding: "6px 12px", borderBottom: "1px solid var(--border)", position: "relative" }}>
        <button
          onClick={() => setDatesOpen((v) => !v)}
          style={{
            background: isFiltered ? "var(--accent-lt)" : "transparent",
            border: `1px solid ${isFiltered ? "var(--accent)" : "var(--border)"}`,
            color: isFiltered ? "var(--accent)" : "var(--muted)",
            borderRadius: "var(--radius)",
            padding: "4px 8px",
            fontSize: 11,
            fontWeight: 500,
            cursor: "pointer",
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 6,
          }}
        >
          <span>
            {isFiltered
              ? `${dateRange.from ?? "…"} → ${dateRange.to ?? "…"}`
              : t.sidebar.filterDates}
          </span>
          <span style={{ fontSize: 9 }}>{datesOpen ? "▲" : "▼"}</span>
        </button>
        {datesOpen && (
          <DateRangePicker
            value={dateRange}
            onApply={(range) => onDateRangeChange(range)}
            onClear={() => onDateRangeChange({ from: null, to: null })}
            onClose={() => setDatesOpen(false)}
          />
        )}
      </div>

      <div style={{ overflowY: "auto", flex: 1 }}>
        {visible.length === 0 && (
          <p style={{ padding: 16, color: "var(--muted)", fontSize: 13 }}>
            {isFiltered ? t.sidebar.noArticlesInRange : t.sidebar.noArticles}
          </p>
        )}
        {visible.map((a) => {
          const isMine = currentUserId && a.author_user_id === currentUserId;
          const isSelected = a.id === selectedId;
          return (
            <button
              key={a.id}
              onClick={() => onSelect(a.id)}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 10,
                width: "100%",
                padding: "10px 12px",
                // 'done' articles stay muted even when selected — readers need to
                // remember the article is already done. Selection still shows
                // through the orange left border + a subtler tint.
                background: isSelected
                  ? a.marked_done
                    ? "rgba(234, 88, 12, 0.06)"
                    : "var(--accent-lt)"
                  : isMine
                    ? "#fff9f5"
                    : "transparent",
                borderLeft: isSelected ? "3px solid var(--accent)" : "3px solid transparent",
                borderTop: "none",
                borderRight: "none",
                borderBottom: "1px solid var(--border)",
                textAlign: "left",
                cursor: "pointer",
                opacity: a.marked_done ? 0.55 : 1,
              }}
            >
              {a.marked_done ? (
                <span style={{ color: "#22c55e", fontWeight: 700, fontSize: 14, flexShrink: 0, lineHeight: 1, marginTop: 3 }}>✓</span>
              ) : (
                <span style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: STATUS_DOT[a.status] ?? "#94a3b8",
                  flexShrink: 0,
                  marginTop: 5,
                }} />
              )}
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {a.topic}
                </div>
                <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2, display: "flex", gap: 6, alignItems: "center" }}>
                  <span>{a.created_at ? new Date(a.created_at).toLocaleDateString(lang) : "—"}</span>
                  {isMine && (
                    <span style={{
                      background: "var(--accent)",
                      color: "var(--white)",
                      borderRadius: 3,
                      padding: "0 4px",
                      fontSize: 10,
                      fontWeight: 600,
                      lineHeight: "16px",
                    }}>
                      {t.sidebar.mine}
                    </span>
                  )}
                </div>
              </div>
            </button>
          );
        })}
        {hasMore && visible.length > 0 && (
          <button
            onClick={onLoadMore}
            disabled={loadingMore}
            style={{
              display: "block",
              width: "100%",
              padding: "10px 12px",
              background: "transparent",
              border: "none",
              borderTop: "1px solid var(--border)",
              fontSize: 12,
              fontWeight: 500,
              color: loadingMore ? "var(--muted)" : "var(--accent)",
              cursor: loadingMore ? "default" : "pointer",
              textAlign: "center",
            }}
          >
            {loadingMore ? t.sidebar.loadingMore : t.sidebar.loadMore}
          </button>
        )}
      </div>
    </aside>
  );
}
