import { apiRequest } from "@/lib/api/client";
import { JobListItem } from "@/types/jobs";
import { DateFilterValue, toApiDateFilterQuery } from "@/lib/date-filter";

export function fetchJobs(dateFilter?: DateFilterValue) {
  if (!dateFilter) {
    return apiRequest<JobListItem[]>("/app/jobs");
  }
  const query = toApiDateFilterQuery(dateFilter) as Record<string, string>;
  const params = new URLSearchParams(query);
  const queryString = params.toString();
  if (!queryString) {
    return apiRequest<JobListItem[]>("/app/jobs");
  }
  return apiRequest<JobListItem[]>(`/app/jobs?${queryString}`);
}
