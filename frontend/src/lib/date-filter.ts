import { parseApiDateTime } from "@/lib/presentation";

export const DATE_PRESETS = [
  "all",
  "today",
  "last_7_days",
  "last_30_days",
  "this_month",
  "previous_month",
  "custom",
] as const;

export type DatePreset = (typeof DATE_PRESETS)[number];

export type DateFilterValue = {
  date: DatePreset;
  start?: string;
  end?: string;
};

export const DEFAULT_DATE_PRESET: DatePreset = "last_7_days";

function pad(value: number) {
  return String(value).padStart(2, "0");
}

export function toIsoDate(date: Date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function parseIsoDate(raw: string | null | undefined): Date | null {
  if (!raw || !/^\d{4}-\d{2}-\d{2}$/.test(raw)) return null;
  const parsed = new Date(`${raw}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function startOfMonth(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function addDays(date: Date, days: number) {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

function presetRange(preset: DatePreset): { start: string; end: string } {
  const today = new Date();
  const end = toIsoDate(today);
  if (preset === "all") return { start: "", end: "" };
  if (preset === "today") return { start: end, end };
  if (preset === "last_30_days") return { start: toIsoDate(addDays(today, -29)), end };
  if (preset === "this_month") return { start: toIsoDate(startOfMonth(today)), end };
  if (preset === "previous_month") {
    const currentStart = startOfMonth(today);
    const previousEnd = addDays(currentStart, -1);
    return {
      start: toIsoDate(startOfMonth(previousEnd)),
      end: toIsoDate(previousEnd),
    };
  }
  return { start: toIsoDate(addDays(today, -6)), end };
}

export function normalizeDateFilter(value: Partial<DateFilterValue>): DateFilterValue {
  const parsedPreset = DATE_PRESETS.includes(value.date as DatePreset)
    ? (value.date as DatePreset)
    : DEFAULT_DATE_PRESET;

  if (parsedPreset === "all") {
    return { date: "all" };
  }

  if (parsedPreset !== "custom") {
    const range = presetRange(parsedPreset);
    return { date: parsedPreset, start: range.start, end: range.end };
  }

  const parsedStart = parseIsoDate(value.start);
  const parsedEnd = parseIsoDate(value.end);
  if (!parsedStart || !parsedEnd || parsedStart > parsedEnd) {
    const range = presetRange(DEFAULT_DATE_PRESET);
    return { date: DEFAULT_DATE_PRESET, start: range.start, end: range.end };
  }
  return { date: "custom", start: toIsoDate(parsedStart), end: toIsoDate(parsedEnd) };
}

export function toApiDateFilterQuery(value: DateFilterValue) {
  const normalized = normalizeDateFilter(value);
  if (normalized.date === "all") {
    return { date: "all" };
  }
  if (normalized.date === "custom") {
    return {
      date: normalized.date,
      start: normalized.start ?? "",
      end: normalized.end ?? "",
    };
  }
  return { date: normalized.date };
}

export function isDateInFilterRange(value: string | null | undefined, filter: DateFilterValue) {
  const normalized = normalizeDateFilter(filter);
  if (normalized.date === "all") {
    return true;
  }
  if (!value) return false;
  const target = parseApiDateTime(value);
  if (Number.isNaN(target.getTime())) return false;

  const start = parseIsoDate(normalized.start);
  const end = parseIsoDate(normalized.end);
  if (!start || !end) return true;

  const targetDate = new Date(target.getFullYear(), target.getMonth(), target.getDate());
  return targetDate >= start && targetDate <= end;
}
