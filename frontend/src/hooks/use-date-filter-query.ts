"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { DateFilterValue, normalizeDateFilter } from "@/lib/date-filter";

export function useDateFilterQuery() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const value = useMemo(
    () =>
      normalizeDateFilter({
        date: searchParams.get("date") ?? undefined,
        start: searchParams.get("start") ?? undefined,
        end: searchParams.get("end") ?? undefined,
      }),
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
