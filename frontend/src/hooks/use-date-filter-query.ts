"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { DATE_PRESETS, DatePreset, DateFilterValue, normalizeDateFilter } from "@/lib/date-filter";

function isDateFilterPreset(value: string | null): value is DatePreset {
  if (!value) {
    return false;
  }
  return DATE_PRESETS.includes(value as DatePreset);
}

export function useDateFilterQuery() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const value = useMemo(
    () => {
      const rawDate = searchParams.get("date");
      const date = isDateFilterPreset(rawDate) ? rawDate : undefined;

      return normalizeDateFilter({
        date,
        start: searchParams.get("start") ?? undefined,
        end: searchParams.get("end") ?? undefined,
      });
    },
    [searchParams],
  );

  const setValue = useCallback(
    (nextValue: DateFilterValue) => {
      const normalized = normalizeDateFilter(nextValue);
      const params = new URLSearchParams(searchParams.toString());

      params.set("date", normalized.date);
      if (normalized.date === "custom") {
        params.set("start", normalized.start ?? "");
        params.set("end", normalized.end ?? "");
      } else {
        params.delete("start");
        params.delete("end");
      }
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  return { value, setValue };
}
