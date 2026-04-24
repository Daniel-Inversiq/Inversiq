"use client";

import { useEffect, useState } from "react";
import { DateFilterValue } from "@/lib/date-filter";
import { cn } from "@/lib/utils";

type DateFilterProps = {
  value: DateFilterValue;
  onChange: (value: DateFilterValue) => void;
  className?: string;
};

export function DateFilter({ value, onChange, className }: DateFilterProps) {
  const [customStart, setCustomStart] = useState(value.start ?? "");
  const [customEnd, setCustomEnd] = useState(value.end ?? "");

  useEffect(() => {
    setCustomStart(value.start ?? "");
    setCustomEnd(value.end ?? "");
  }, [value.end, value.start]);

  return (
    <div
      className={cn(
        "flex flex-wrap items-end gap-2 rounded-xl border border-zinc-200/90 bg-white p-3",
        className,
      )}
    >
      <label className="flex min-w-[180px] flex-col gap-1 text-[11px] font-semibold uppercase tracking-[0.06em] text-zinc-500">
        Datum
        <select
          value={value.date}
          onChange={(event) => onChange({ date: event.target.value as DateFilterValue["date"] })}
          className="h-9 rounded-lg border border-zinc-200 bg-white px-2 text-[13px] font-medium text-zinc-700 outline-none ring-primary/20 focus:ring-2"
        >
          <option value="all">Alles</option>
          <option value="today">Vandaag</option>
          <option value="last_7_days">Laatste 7 dagen</option>
          <option value="last_30_days">Laatste 30 dagen</option>
          <option value="this_month">Deze maand</option>
          <option value="previous_month">Vorige maand</option>
          <option value="custom">Aangepast</option>
        </select>
      </label>

      {value.date === "custom" ? (
        <>
          <label className="flex min-w-[140px] flex-col gap-1 text-[11px] font-semibold uppercase tracking-[0.06em] text-zinc-500">
            Van
            <input
              type="date"
              value={customStart}
              onChange={(event) => setCustomStart(event.target.value)}
              className="h-9 rounded-lg border border-zinc-200 bg-white px-2 text-[13px] font-medium text-zinc-700 outline-none ring-primary/20 focus:ring-2"
            />
          </label>
          <label className="flex min-w-[140px] flex-col gap-1 text-[11px] font-semibold uppercase tracking-[0.06em] text-zinc-500">
            Tot
            <input
              type="date"
              value={customEnd}
              onChange={(event) => setCustomEnd(event.target.value)}
              className="h-9 rounded-lg border border-zinc-200 bg-white px-2 text-[13px] font-medium text-zinc-700 outline-none ring-primary/20 focus:ring-2"
            />
          </label>
          <button
            type="button"
            onClick={() => onChange({ date: "custom", start: customStart, end: customEnd })}
            className="h-9 rounded-lg border border-zinc-200 px-3 text-[13px] font-semibold text-zinc-700 hover:bg-zinc-50"
          >
            Toepassen
          </button>
        </>
      ) : null}
    </div>
  );
}
