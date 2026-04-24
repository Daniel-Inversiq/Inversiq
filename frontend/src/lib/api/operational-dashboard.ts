import { apiRequest } from "@/lib/api/client";
import type { OperationalDashboardResponse } from "@/types/operational-dashboard";

export function fetchOperationalDashboard(params: {
  chartDays: number;
  /** Same as `-new Date().getTimezoneOffset()` (minutes east of UTC). */
  timezoneOffsetMinutes: number;
}) {
  const sp = new URLSearchParams();
  sp.set("chart_days", String(params.chartDays));
  sp.set("timezone_offset_minutes", String(params.timezoneOffsetMinutes));
  return apiRequest<OperationalDashboardResponse>(
    `/app/api/dashboard/operational?${sp.toString()}`,
  );
}
