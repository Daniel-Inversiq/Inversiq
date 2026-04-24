import { apiRequest } from "@/lib/api/client";
import { ActivityPayload, DashboardSummary } from "@/types/dashboard";

export function fetchDashboardSummary() {
  return apiRequest<DashboardSummary>("/app/api/dashboard/summary");
}

export function fetchDashboardActivity() {
  return apiRequest<ActivityPayload>("/app/api/dashboard/activity");
}
