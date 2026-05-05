// frontend/src/lib/datePresets.ts
// Date range presets shared between the sidebar picker and useArticles
// (default selection). Pure / no React. ISO 'YYYY-MM-DD' strings on the
// boundary so the API contract stays simple.

import type { Translations } from "../i18n/types";
import type { DateRange } from "./useArticles";

export type PresetId =
  | "today"
  | "yesterday"
  | "thisWeek"
  | "last7"
  | "lastWeek"
  | "thisMonth"
  | "last30"
  | "lastMonth";

export const PRESET_IDS: PresetId[] = [
  "today",
  "yesterday",
  "thisWeek",
  "last7",
  "lastWeek",
  "thisMonth",
  "last30",
  "lastMonth",
];

export function toISODate(d: Date): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export function parseISODate(iso: string | null): Date | undefined {
  if (!iso) return undefined;
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** Compute the (from, to) Date pair for a preset relative to today. */
export function computePreset(id: PresetId, today: Date = new Date()): { from: Date; to: Date } {
  const t = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  switch (id) {
    case "today":
      return { from: t, to: t };
    case "yesterday": {
      const y = new Date(t);
      y.setDate(y.getDate() - 1);
      return { from: y, to: y };
    }
    case "thisWeek": {
      const day = (t.getDay() + 6) % 7; // 0 = Mon
      const start = new Date(t);
      start.setDate(start.getDate() - day);
      return { from: start, to: t };
    }
    case "last7": {
      const start = new Date(t);
      start.setDate(start.getDate() - 6); // inclusive of today => 7 days total
      return { from: start, to: t };
    }
    case "lastWeek": {
      const day = (t.getDay() + 6) % 7;
      const thisMon = new Date(t);
      thisMon.setDate(thisMon.getDate() - day);
      const lastMon = new Date(thisMon);
      lastMon.setDate(lastMon.getDate() - 7);
      const lastSun = new Date(thisMon);
      lastSun.setDate(lastSun.getDate() - 1);
      return { from: lastMon, to: lastSun };
    }
    case "thisMonth": {
      const start = new Date(t.getFullYear(), t.getMonth(), 1);
      return { from: start, to: t };
    }
    case "last30": {
      const start = new Date(t);
      start.setDate(start.getDate() - 29);
      return { from: start, to: t };
    }
    case "lastMonth": {
      const start = new Date(t.getFullYear(), t.getMonth() - 1, 1);
      const end = new Date(t.getFullYear(), t.getMonth(), 0);
      return { from: start, to: end };
    }
  }
}

/** Same shape as `computePreset`, but returns ISO strings ready for `DateRange`. */
export function computePresetRange(id: PresetId, today?: Date): DateRange {
  const { from, to } = computePreset(id, today);
  return { from: toISODate(from), to: toISODate(to) };
}

/** Identify which preset (if any) the current range corresponds to. */
export function detectPreset(range: DateRange, today: Date = new Date()): PresetId | null {
  if (!range.from || !range.to) return null;
  for (const id of PRESET_IDS) {
    const p = computePresetRange(id, today);
    if (p.from === range.from && p.to === range.to) return id;
  }
  return null;
}

/** Human-readable label for the range button.
 * - matches a preset → translated preset label
 * - custom range with both bounds → 'D MMM – D MMM YYYY'
 * - one-sided / null bounds → t.sidebar.filterDates fallback */
export function formatRangeLabel(
  range: DateRange,
  t: Translations,
  lang: string,
): string {
  if (!range.from && !range.to) return t.sidebar.filterDates;
  const presetId = detectPreset(range);
  if (presetId) return t.datePicker[presetId];
  const fmt = new Intl.DateTimeFormat(lang, { day: "numeric", month: "short", year: "numeric" });
  const fromDate = parseISODate(range.from);
  const toDate = parseISODate(range.to);
  if (fromDate && toDate) {
    return `${fmt.format(fromDate)} – ${fmt.format(toDate)}`;
  }
  if (fromDate) return `${t.datePicker.from} ${fmt.format(fromDate)}`;
  if (toDate) return `${t.datePicker.to} ${fmt.format(toDate)}`;
  return t.sidebar.filterDates;
}
