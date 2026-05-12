import { useRef, useState } from "react";
import type { ArticleListItem } from "../types";
import type { DateRange } from "../lib/useArticles";
import { formatRangeLabel } from "../lib/datePresets";
import { useT, useLang } from "../i18n";
import { DateRangePicker } from "./DateRangePicker";
import { Button } from "./ui/Button";

const STATUS_DOT: Record<string, string> = {
  done: "var(--success)",
  running: "var(--warning)",
  failed: "var(--error)",
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
  open: boolean;
  isMobile: boolean;
  onClose: () => void;
  onExpand: () => void;
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
  open,
  isMobile,
  onClose,
  onExpand,
}: SidebarProps) {
  const t = useT();
  const { lang } = useLang();
  const [onlyMine, setOnlyMine] = useState(false);
  const [doneFilter, setDoneFilter] = useState<DoneFilter>("all");
  const [datesOpen, setDatesOpen] = useState(false);
  const datesAnchorRef = useRef<HTMLButtonElement>(null);

  const visible = articles
    .filter((a) => !onlyMine || !currentUserId || a.author_user_id === currentUserId)
    .filter((a) => doneFilter === "all" ? true : doneFilter === "done" ? a.marked_done : !a.marked_done);

  const labels: Record<DoneFilter, string> = {
    all: t.sidebar.filterAll,
    undone: t.sidebar.filterUndone,
    done: t.sidebar.filterDone,
  };

  // ── Collapsed rail (desktop only) ─────────────────────────────────────────
  // When the user closes the sidebar on desktop we still keep a 48px rail
  // anchored to the left edge so the new-article button and the expand
  // affordance are always one click away.
  if (!open && !isMobile) {
    return (
      <aside style={{
        width: 48,
        background: "var(--sidebar)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "8px 0",
        gap: 8,
      }}>
        <button
          onClick={onExpand}
          aria-label={t.sidebar.articles}
          title={t.sidebar.articles}
          style={{
            background: "none",
            border: "none",
            padding: 8,
            cursor: "pointer",
            color: "var(--muted)",
            borderRadius: "var(--radius)",
          }}
        >
          {/* Right-pointing chevron — 'expand to show list' */}
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>
        <button
          onClick={onNew}
          aria-label={t.sidebar.newArticle}
          title={t.sidebar.newArticle}
          style={{
            background: "var(--accent)",
            color: "#fff",
            border: "none",
            borderRadius: "var(--radius)",
            width: 32,
            height: 32,
            fontSize: 18,
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
          }}
        >
          +
        </button>
      </aside>
    );
  }

  // ── Mobile drawer (overlay + backdrop) — rendered only when open ──────────
  // Hidden state on mobile == nothing rendered so the article view gets the
  // full screen. Backdrop click closes.
  if (isMobile && !open) {
    return null;
  }

  const containerStyle: React.CSSProperties = isMobile
    ? {
        position: "fixed",
        top: 48, // below topbar
        left: 0,
        bottom: 0,
        width: "min(85vw, 320px)",
        background: "var(--sidebar)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        zIndex: 60,
        boxShadow: "2px 0 12px rgba(0,0,0,0.12)",
      }
    : {
        width: "var(--sidebar-width)",
        background: "var(--sidebar)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      };

  return (
    <>
      {isMobile && (
        <div
          onClick={onClose}
          style={{
            position: "fixed",
            top: 48,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.4)",
            zIndex: 55,
          }}
        />
      )}
      <aside style={containerStyle}>
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
        <Button variant="primary" size="sm" onClick={onNew}>
          {t.sidebar.newArticle}
        </Button>
      </div>

      <div style={{ padding: "6px 12px", borderBottom: "1px solid var(--border)", display: "flex", gap: 6, flexWrap: "wrap" }}>
        {(["all", "undone", "done"] as DoneFilter[]).map((f) => {
          const active = doneFilter === f;
          return (
            <button key={f} onClick={() => setDoneFilter(f)} style={{
              background: active ? "var(--accent)" : "transparent",
              color: active ? "#fff" : "var(--muted)",
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
            color: onlyMine ? "#fff" : "var(--muted)",
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
          presets on the left and a two-month calendar on the right. The
          popover renders through a portal so it can escape the sidebar's
          overflow:hidden and the page's right edge. */}
      <div style={{ padding: "6px 12px", borderBottom: "1px solid var(--border)" }}>
        <button
          ref={datesAnchorRef}
          onClick={() => setDatesOpen((v) => !v)}
          style={{
            background: "transparent",
            border: "1px solid var(--border)",
            color: "var(--muted)",
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
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {formatRangeLabel(dateRange, t, lang)}
          </span>
          <span style={{ fontSize: 9 }}>{datesOpen ? "▲" : "▼"}</span>
        </button>
        {datesOpen && (
          <DateRangePicker
            anchorEl={datesAnchorRef.current}
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
                  : "transparent",
                borderLeft: isSelected ? "3px solid var(--accent)" : "3px solid transparent",
                borderTop: "none",
                borderRight: "none",
                borderBottom: "1px solid var(--border)",
                textAlign: "left",
                cursor: "pointer",
                transition: "background 0.12s",
                // Done = strong dim, failed = subtle dim. Failed shouldn't
                // shout — the red ✕ already signals state, opacity just keeps
                // it from competing with active (running/done) entries.
                opacity: a.marked_done
                  ? 0.55
                  : (a.status === "failed" || a.status === "insufficient_sources")
                    ? 0.65
                    : 1,
              }}
            >
              {a.marked_done ? (
                <span style={{ color: "var(--success)", fontWeight: 700, fontSize: 14, flexShrink: 0, lineHeight: 1, marginTop: 3 }}>✓</span>
              ) : (a.status === "failed" || a.status === "insufficient_sources") ? (
                // Red disc with white ✕ — clearly different from the orange/green
                // dots so failed articles read at a glance in a long list.
                <span style={{
                  width: 14,
                  height: 14,
                  borderRadius: "50%",
                  background: "var(--error)",
                  color: "#fff",
                  fontSize: 10,
                  fontWeight: 700,
                  flexShrink: 0,
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginTop: 2,
                  lineHeight: 1,
                }}>✕</span>
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
                      color: "#fff",
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
    </>
  );
}
