import { apiRequest } from "@/lib/api/client";
import { UploadListItem } from "@/types/uploads";

export function fetchUploads() {
  return apiRequest<UploadListItem[]>("/app/uploads");
}
