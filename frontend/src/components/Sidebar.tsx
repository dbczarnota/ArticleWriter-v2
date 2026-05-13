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
  if (!open && !isMobile) {
    return (
      <aside style={{
        width: 48,
        background: "var(--sidebar)",
        borderRight: "1px solid var(--chrome-border)",
        color: "var(--chrome-ink)",
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
            color: "var(--chrome-muted)",
            borderRadius: "var(--radius)",
          }}
        >
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

  // ── Mobile drawer ─────────────────────────────────────────────────────────
  if (isMobile && !open) {
    return null;
  }

  const containerStyle: React.CSSProperties = isMobile
    ? {
        position: "fixed",
        top: 56,
        left: 0,
        bottom: 0,
        width: "min(85vw, 320px)",
        background: "var(--sidebar)",
        borderRight: "1px solid var(--chrome-border)",
        color: "var(--chrome-ink)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        zIndex: 60,
        boxShadow: "4px 0 24px rgba(0,0,0,0.35)",
      }
    : {
        width: "var(--sidebar-width)",
        background: "var(--sidebar)",
        borderRight: "1px solid var(--chrome-border)",
        color: "var(--chrome-ink)",
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

        {/* sidebar-head: title row + filter chips + date range — one grouped block */}
        <div style={{
          padding: "16px 16px 12px",
          display: "flex",
          flexDirection: "column",
          gap: 12,
          borderBottom: "1px solid var(--chrome-border)",
        }}>
          {/* sb-row: title + new button */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--chrome-subtle)", textTransform: "uppercase", letterSpacing: ".12em" }}>
              {t.sidebar.articles}
            </span>
            <Button
              variant="primary"
              size="sm"
              onClick={onNew}
              style={{ fontSize: 12 }}
              iconLeft={<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>}
            >
              {t.sidebar.newArticle}
            </Button>
          </div>

          {/* filter-chips */}
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {(["all", "undone", "done"] as DoneFilter[]).map((f) => {
              const active = doneFilter === f;
              return (
                <button key={f} onClick={() => setDoneFilter(f)} style={{
                  background: active ? "var(--accent)" : "transparent",
                  color: active ? "#fff" : "var(--chrome-muted)",
                  border: active ? "1px solid var(--accent)" : "1px solid var(--chrome-border)",
                  borderRadius: 999,
                  padding: "4px 9px",
                  fontSize: 11,
                  fontWeight: active ? 600 : 500,
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}>{labels[f]}</button>
              );
            })}
            {currentUserId && (
              <button onClick={() => setOnlyMine((v) => !v)} style={{
                background: onlyMine ? "var(--accent)" : "transparent",
                color: onlyMine ? "#fff" : "var(--chrome-muted)",
                border: onlyMine ? "1px solid var(--accent)" : "1px solid var(--chrome-border)",
                borderRadius: 999,
                padding: "4px 9px",
                fontSize: 11,
                fontWeight: onlyMine ? 600 : 500,
                cursor: "pointer",
                fontFamily: "inherit",
              }}>{t.sidebar.filterMine}</button>
            )}
          </div>

          {/* date range — styled like mockup .sb-select */}
          <div>
            <button
              ref={datesAnchorRef}
              onClick={() => setDatesOpen((v) => !v)}
              style={{
                background: "var(--chrome-bg)",
                border: "1px solid var(--chrome-border)",
                color: "var(--chrome-muted)",
                borderRadius: "var(--radius)",
                padding: "6px 10px",
                fontSize: 12,
                fontWeight: 500,
                cursor: "pointer",
                width: "100%",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 6,
                fontFamily: "inherit",
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
        </div>

        {/* article list */}
        <div className="chrome-scroll" style={{ overflowY: "auto", flex: 1, padding: 8 }}>
          {visible.length === 0 && (
            <p style={{ padding: 16, color: "var(--chrome-muted)", fontSize: 13 }}>
              {isFiltered ? t.sidebar.noArticlesInRange : t.sidebar.noArticles}
            </p>
          )}
          {visible.map((a) => {
            const isMine = currentUserId && a.author_user_id === currentUserId;
            const isSelected = a.id === selectedId;
            const isRunning = a.status === "running" && !a.marked_done;
            const isFailed = (a.status === "failed" || a.status === "insufficient_sources") && !a.marked_done;
            const dotColor = isFailed ? "var(--error)" : (STATUS_DOT[a.status] ?? "#94a3b8");
            return (
              <button
                key={a.id}
                onClick={() => onSelect(a.id)}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  width: "100%",
                  padding: "10px 12px 10px 14px",
                  marginBottom: 2,
                  borderRadius: 6,
                  position: "relative",
                  background: isSelected ? "rgba(234,88,12,.08)" : "transparent",
                  border: "none",
                  textAlign: "left",
                  cursor: "pointer",
                  transition: "background 0.12s",
                }}
              >
                {isSelected && (
                  <span style={{
                    position: "absolute", left: 0, top: 8, bottom: 8,
                    width: 3, background: "var(--accent)", borderRadius: "0 2px 2px 0",
                  }} />
                )}
                <div style={{ fontSize: 13, fontWeight: a.marked_done ? 400 : 500, lineHeight: 1.4, color: a.marked_done ? "var(--chrome-muted)" : "var(--chrome-ink)", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                  {a.topic}
                </div>
                <div style={{ fontSize: 11, color: "var(--chrome-subtle)", display: "flex", gap: 8, alignItems: "center" }}>
                  {a.marked_done ? (
                    <span style={{ color: "var(--success)", fontWeight: 700, fontSize: 12, lineHeight: 1 }}>✓</span>
                  ) : (
                    <span style={{
                      width: 6, height: 6, borderRadius: "50%", background: dotColor,
                      flexShrink: 0, display: "inline-block",
                      animation: isRunning ? "pulse-dot 1.8s ease-out infinite" : undefined,
                    }} />
                  )}
                  {isRunning ? (
                    <span>{t.sidebar.statusRunning}</span>
                  ) : isFailed ? (
                    <span>{t.sidebar.statusFailed}</span>
                  ) : (
                    <span>{a.created_at ? new Date(a.created_at).toLocaleDateString(lang) : "—"}</span>
                  )}
                  {isMine && (
                    <span style={{
                      background: "rgba(234,88,12,.12)",
                      color: "var(--accent-light)",
                      borderRadius: 4,
                      border: "none",
                      padding: "1px 6px",
                      fontSize: 9,
                      fontWeight: 700,
                      letterSpacing: ".08em",
                      textTransform: "uppercase",
                    }}>
                      {t.sidebar.mine}
                    </span>
                  )}
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
                borderTop: "1px solid var(--chrome-border)",
                fontSize: 12,
                fontWeight: 500,
                color: loadingMore ? "var(--chrome-subtle)" : "var(--accent)",
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