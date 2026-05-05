// frontend/src/components/DateRangePicker.tsx
// Two-month range picker with a left rail of common presets.
// Designed to feel native to the rest of the app — soft borders,
// accent-tinted selection, no heavy outlines.
//
// Implementation note: tokens.css applies a global `*, *::before, *::after
// { margin: 0; padding: 0; }` reset that wipes react-day-picker's internal
// spacing. Every layout-critical class below restores the values explicitly
// so the grid renders correctly inside this app.

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { DayPicker } from "react-day-picker";
import type { DateRange as RDPDateRange } from "react-day-picker";
import "react-day-picker/dist/style.css";
import { useT, useLang } from "../i18n";
import {
  computePreset,
  parseISODate,
  toISODate,
  type PresetId,
} from "../lib/datePresets";
import { useMediaQuery } from "../lib/useMediaQuery";
import type { DateRange } from "../lib/useArticles";

interface DateRangePickerProps {
  /** Element the popover anchors below (or fills the screen on mobile). */
  anchorEl: HTMLElement | null;
  value: DateRange;
  onApply: (range: DateRange) => void;
  onClear: () => void;
  onClose: () => void;
}

export function DateRangePicker({
  anchorEl,
  value,
  onApply,
  onClear,
  onClose,
}: DateRangePickerProps) {
  const t = useT();
  const { lang } = useLang();
  const narrow = useMediaQuery("(max-width: 767px)");
  const [draft, setDraft] = useState<RDPDateRange | undefined>(() => ({
    from: parseISODate(value.from),
    to: parseISODate(value.to),
  }));
  // Strict cycle: click 1 = from, click 2 = to, click 3 = new from, click 4 = to.
  // 0 → next click sets `from`; 1 → next click sets `to`.
  const [clickStep, setClickStep] = useState<0 | 1>(0);
  const rootRef = useRef<HTMLDivElement>(null);

  // Click outside closes (Apply/Cancel/Clear handle their own close).
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [onClose]);

  const presets: Array<{ id: PresetId; label: string }> = [
    { id: "today", label: t.datePicker.today },
    { id: "yesterday", label: t.datePicker.yesterday },
    { id: "thisWeek", label: t.datePicker.thisWeek },
    { id: "last7", label: t.datePicker.last7 },
    { id: "lastWeek", label: t.datePicker.lastWeek },
    { id: "thisMonth", label: t.datePicker.thisMonth },
    { id: "last30", label: t.datePicker.last30 },
    { id: "lastMonth", label: t.datePicker.lastMonth },
  ];

  function applyPreset(id: PresetId) {
    const { from, to } = computePreset(id);
    setDraft({ from, to });
    setClickStep(0);
  }

  function handleDayClick(day: Date) {
    if (clickStep === 0) {
      setDraft({ from: day, to: undefined });
      setClickStep(1);
    } else {
      const from = draft?.from;
      if (from && day < from) {
        // Second click before current `from` — flip so range stays valid.
        setDraft({ from: day, to: from });
      } else {
        setDraft({ from: from ?? day, to: day });
      }
      setClickStep(0);
    }
  }

  function handleApply() {
    onApply({
      from: draft?.from ? toISODate(draft.from) : null,
      to: draft?.to ? toISODate(draft.to) : null,
    });
    onClose();
  }

  function handleClear() {
    setDraft(undefined);
    onClear();
    onClose();
  }

  // Two months on desktop, one on mobile (mobile-only fallback to keep the
  // popover from overflowing the viewport).
  const today = new Date();
  const numberOfMonths = narrow ? 1 : 2;
  const defaultMonth = narrow
    ? new Date(today.getFullYear(), today.getMonth(), 1)
    : new Date(today.getFullYear(), today.getMonth() - 1, 1);

  // Width math:
  //   left rail = 140 px
  //   each month = 7 cols × 36 px = 252 px + 16 px horizontal padding
  //   inter-month gap from react-day-picker = 16 px
  //   borders + breathing room ≈ 8 px
  // Two months: 140 + 252 + 252 + 16 + 24 = 684 px → round to 700.
  // One month: 140 + 252 + 24 = 416 px → round to 420.
  const popoverWidth = narrow ? 320 : 700;

  // Compute fixed position relative to the anchor button. Recomputes on
  // window resize/scroll so the popover stays glued to the anchor while
  // the user interacts with the page.
  const [pos, setPos] = useState<{ top: number; left: number; maxHeight: number } | null>(null);
  useLayoutEffect(() => {
    if (!anchorEl) return;
    function reposition() {
      if (!anchorEl) return;
      const rect = anchorEl.getBoundingClientRect();
      const margin = 8; // breathing room from viewport edges
      let left = rect.left;
      // Keep the popover fully on-screen on the right side
      if (left + popoverWidth + margin > window.innerWidth) {
        left = Math.max(margin, window.innerWidth - popoverWidth - margin);
      }
      const top = rect.bottom + 4;
      // Clamp the popover height to whatever fits below the anchor so the
      // bottom bar (Apply / Cancel / Clear) is always reachable without
      // page scroll. Internal area scrolls if presets + calendar exceed it.
      const maxHeight = Math.max(280, window.innerHeight - top - margin);
      setPos({ top, left, maxHeight });
    }
    reposition();
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    return () => {
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
    };
  }, [anchorEl, popoverWidth, narrow]);

  if (!pos) return null;

  return createPortal(
    <div
      ref={rootRef}
      style={{
        position: "fixed",
        top: pos.top,
        left: pos.left,
        zIndex: 1000,
        background: "var(--white)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        boxShadow: "0 8px 24px rgba(0,0,0,0.08)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        width: popoverWidth,
        maxWidth: "calc(100vw - 24px)",
        maxHeight: pos.maxHeight,
      }}
    >
      <style>{`
        /* Restore margins/padding the global reset stripped, then layer accent. */
        .hf-rdp { --rdp-accent-color: var(--accent); --rdp-accent-background-color: var(--accent-lt); }
        .hf-rdp .rdp-months { display: flex; gap: 16px; padding: 8px 12px; flex-wrap: wrap; }
        .hf-rdp .rdp-month { display: block; }
        .hf-rdp .rdp-month_caption { font-size: 13px; font-weight: 600; padding: 4px 0 8px; }
        .hf-rdp .rdp-nav { padding: 0 4px; }
        .hf-rdp .rdp-button_previous,
        .hf-rdp .rdp-button_next {
          width: 28px; height: 28px; padding: 0; color: var(--muted);
          display: inline-flex; align-items: center; justify-content: center;
          background: transparent; border-radius: 4px;
        }
        .hf-rdp .rdp-button_previous:hover,
        .hf-rdp .rdp-button_next:hover { background: var(--accent-lt); color: var(--accent); }
        .hf-rdp .rdp-month_grid { border-collapse: separate; border-spacing: 0; }
        .hf-rdp .rdp-weekdays { display: table-row; }
        .hf-rdp .rdp-weekday {
          width: 36px; height: 28px; padding: 0;
          font-size: 11px; color: var(--muted); font-weight: 500;
          text-transform: none;
        }
        .hf-rdp .rdp-week { display: table-row; }
        .hf-rdp .rdp-day { width: 36px; height: 36px; padding: 1px; text-align: center; vertical-align: middle; }
        .hf-rdp .rdp-day_button {
          width: 34px; height: 34px; padding: 0; margin: 0;
          font: inherit; font-size: 12px;
          background: transparent; color: var(--text); border: none;
          border-radius: 4px;
          cursor: pointer;
          display: inline-flex; align-items: center; justify-content: center;
        }
        .hf-rdp .rdp-day_button:hover:not([aria-disabled="true"]) {
          background: var(--accent-lt); color: var(--accent);
        }
        .hf-rdp .rdp-today .rdp-day_button:not([aria-selected="true"]) {
          color: var(--accent); font-weight: 600;
        }
        /* Range middle: full-bleed light background, no per-cell radius. */
        .hf-rdp .rdp-range_middle { background: var(--accent-lt); }
        .hf-rdp .rdp-range_middle .rdp-day_button {
          background: transparent; color: var(--text); border-radius: 0; width: 100%;
        }
        /* Range start / end: solid accent disc. */
        .hf-rdp .rdp-range_start .rdp-day_button,
        .hf-rdp .rdp-range_end .rdp-day_button,
        .hf-rdp .rdp-selected:not(.rdp-range_middle) .rdp-day_button {
          background: var(--accent); color: var(--white); border: none; border-radius: 4px;
        }
        .hf-rdp .rdp-day_button:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
        .hf-rdp .rdp-disabled .rdp-day_button { color: var(--muted); opacity: 0.4; cursor: default; }
        .hf-rdp .rdp-outside .rdp-day_button { color: var(--muted); opacity: 0.5; }
      `}</style>
      <div style={{ display: "flex", flexDirection: narrow ? "column" : "row", flex: 1, minHeight: 0, overflow: "auto" }}>
        {/* Left rail — presets */}
        <div
          style={{
            width: narrow ? "100%" : 140,
            borderRight: narrow ? "none" : "1px solid var(--border)",
            borderBottom: narrow ? "1px solid var(--border)" : "none",
            padding: narrow ? "4px" : "8px 0",
            display: "flex",
            flexDirection: narrow ? "row" : "column",
            flexWrap: narrow ? "wrap" : "nowrap",
            gap: narrow ? 4 : 0,
          }}
        >
          {presets.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => applyPreset(p.id)}
              style={{
                background: "none",
                border: narrow ? "1px solid var(--border)" : "none",
                borderRadius: "var(--radius)",
                textAlign: "left",
                padding: narrow ? "4px 8px" : "8px 14px",
                fontSize: 12,
                color: "var(--text)",
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--accent-lt)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Right — calendar */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <DayPicker
            mode="range"
            numberOfMonths={numberOfMonths}
            defaultMonth={defaultMonth}
            selected={draft}
            onDayClick={handleDayClick}
            weekStartsOn={1}
            className="hf-rdp"
            lang={lang}
          />
        </div>
      </div>

      {/* Bottom bar — sticky to popover regardless of inner scroll */}
      <div
        style={{
          borderTop: "1px solid var(--border)",
          padding: "8px 12px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          background: "var(--sidebar)",
          flexShrink: 0,
        }}
      >
        <button
          type="button"
          onClick={handleClear}
          style={{
            background: "none",
            border: "none",
            color: "var(--muted)",
            fontSize: 12,
            cursor: "pointer",
            padding: "4px 8px",
          }}
        >
          {t.datePicker.clear}
        </button>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: "none",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              padding: "4px 12px",
              fontSize: 12,
              color: "var(--text)",
              cursor: "pointer",
            }}
          >
            {t.datePicker.cancel}
          </button>
          <button
            type="button"
            onClick={handleApply}
            style={{
              background: "var(--accent)",
              color: "var(--white)",
              border: "none",
              borderRadius: "var(--radius)",
              padding: "4px 12px",
              fontSize: 12,
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            {t.datePicker.apply}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
