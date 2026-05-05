// frontend/src/components/DateRangePicker.tsx
// Two-month range picker with a left rail of common presets
// (Today / Yesterday / This week / Last 7 days / Last week / This month
// / Last 30 days / Last month). Designed to feel native to the rest of
// the app — no heavy outlines, accent-tinted selection, soft borders.

import { useEffect, useRef, useState } from "react";
import { DayPicker } from "react-day-picker";
import type { DateRange as RDPDateRange } from "react-day-picker";
import "react-day-picker/dist/style.css";
import { useT, useLang } from "../i18n";
import type { DateRange } from "../lib/useArticles";

function toISODate(d: Date): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function parseISODate(iso: string | null): Date | undefined {
  if (!iso) return undefined;
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

type PresetId =
  | "today"
  | "yesterday"
  | "thisWeek"
  | "last7"
  | "lastWeek"
  | "thisMonth"
  | "last30"
  | "lastMonth";

function computePreset(id: PresetId): { from: Date; to: Date } {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  switch (id) {
    case "today":
      return { from: today, to: today };
    case "yesterday": {
      const y = new Date(today);
      y.setDate(y.getDate() - 1);
      return { from: y, to: y };
    }
    case "thisWeek": {
      // Monday-anchored week (matches PL/EN locale convention in this app)
      const day = (today.getDay() + 6) % 7; // 0 = Mon, 6 = Sun
      const start = new Date(today);
      start.setDate(start.getDate() - day);
      return { from: start, to: today };
    }
    case "last7": {
      const start = new Date(today);
      start.setDate(start.getDate() - 6); // includes today, total 7 days
      return { from: start, to: today };
    }
    case "lastWeek": {
      const day = (today.getDay() + 6) % 7;
      const thisMon = new Date(today);
      thisMon.setDate(thisMon.getDate() - day);
      const lastMon = new Date(thisMon);
      lastMon.setDate(lastMon.getDate() - 7);
      const lastSun = new Date(thisMon);
      lastSun.setDate(lastSun.getDate() - 1);
      return { from: lastMon, to: lastSun };
    }
    case "thisMonth": {
      const start = new Date(today.getFullYear(), today.getMonth(), 1);
      return { from: start, to: today };
    }
    case "last30": {
      const start = new Date(today);
      start.setDate(start.getDate() - 29);
      return { from: start, to: today };
    }
    case "lastMonth": {
      const start = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      const end = new Date(today.getFullYear(), today.getMonth(), 0);
      return { from: start, to: end };
    }
  }
}

interface DateRangePickerProps {
  value: DateRange;
  onApply: (range: DateRange) => void;
  onClear: () => void;
  onClose: () => void;
}

export function DateRangePicker({ value, onApply, onClear, onClose }: DateRangePickerProps) {
  const t = useT();
  const { lang } = useLang();
  const [draft, setDraft] = useState<RDPDateRange | undefined>(() => ({
    from: parseISODate(value.from),
    to: parseISODate(value.to),
  }));
  const rootRef = useRef<HTMLDivElement>(null);

  // Click outside closes (but Apply/Clear handle their own close)
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

  // Render two months side by side, with the right pane showing the current
  // month so users see the present and the recent past at the same time.
  const today = new Date();
  const defaultMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);

  return (
    <div
      ref={rootRef}
      style={{
        position: "absolute",
        top: "calc(100% + 4px)",
        left: 0,
        zIndex: 1000,
        background: "var(--white)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        boxShadow: "0 8px 24px rgba(0,0,0,0.08)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <style>{`
        .hf-rdp { --rdp-accent-color: var(--accent); --rdp-accent-background-color: var(--accent-lt); margin: 0; }
        .hf-rdp .rdp-day_button { border-radius: 4px; }
        .hf-rdp .rdp-selected:not(.rdp-range_middle) .rdp-day_button { background: var(--accent); color: var(--white); border: none; }
        .hf-rdp .rdp-range_start .rdp-day_button,
        .hf-rdp .rdp-range_end .rdp-day_button { background: var(--accent); color: var(--white); }
        .hf-rdp .rdp-range_middle { background: var(--accent-lt); }
        .hf-rdp .rdp-range_middle .rdp-day_button { color: var(--text); background: transparent; }
        .hf-rdp .rdp-today .rdp-day_button:not([aria-selected="true"]) { color: var(--accent); font-weight: 600; }
        .hf-rdp .rdp-month_caption { font-size: 13px; font-weight: 600; }
        .hf-rdp .rdp-weekday { font-size: 11px; color: var(--muted); font-weight: 500; }
        .hf-rdp .rdp-button_previous, .hf-rdp .rdp-button_next { color: var(--muted); }
        .hf-rdp .rdp-day_button:hover:not([aria-disabled="true"]) { background: var(--accent-lt); }
      `}</style>
      <div style={{ display: "flex" }}>
        {/* Left rail — presets */}
        <div
          style={{
            width: 140,
            borderRight: "1px solid var(--border)",
            padding: "8px 0",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {presets.map((p) => (
            <button
              key={p.id}
              onClick={() => applyPreset(p.id)}
              style={{
                background: "none",
                border: "none",
                textAlign: "left",
                padding: "8px 14px",
                fontSize: 12,
                color: "var(--text)",
                cursor: "pointer",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--accent-lt)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Right — calendar */}
        <div style={{ padding: "8px 12px" }}>
          <DayPicker
            mode="range"
            numberOfMonths={2}
            defaultMonth={defaultMonth}
            selected={draft}
            onSelect={setDraft}
            weekStartsOn={1}
            locale={undefined /* native locale via lang prop */}
            className="hf-rdp"
            lang={lang}
          />
        </div>
      </div>

      {/* Bottom bar */}
      <div
        style={{
          borderTop: "1px solid var(--border)",
          padding: "8px 12px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          background: "var(--sidebar)",
        }}
      >
        <button
          onClick={handleClear}
          style={{
            background: "none",
            border: "none",
            color: "var(--muted)",
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          {t.datePicker.clear}
        </button>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              padding: "4px 12px",
              fontSize: 12,
              color: "var(--text)",
            }}
          >
            {t.datePicker.cancel}
          </button>
          <button
            onClick={handleApply}
            style={{
              background: "var(--accent)",
              color: "var(--white)",
              border: "none",
              borderRadius: "var(--radius)",
              padding: "4px 12px",
              fontSize: 12,
              fontWeight: 500,
            }}
          >
            {t.datePicker.apply}
          </button>
        </div>
      </div>
    </div>
  );
}
