/** Monday-based week; all operations use the browser local timezone. */

export function startOfWeekMonday(reference: Date): Date {
  const c = new Date(reference);
  c.setHours(0, 0, 0, 0);
  const day = c.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  c.setDate(c.getDate() + diff);
  return c;
}

export function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

export function dateKeyLocal(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function scheduledDateKey(iso: string | null | undefined): string | null {
  if (!iso) {
    return null;
  }
  const t = new Date(iso);
  if (Number.isNaN(t.getTime())) {
    return null;
  }
  return dateKeyLocal(t);
}
