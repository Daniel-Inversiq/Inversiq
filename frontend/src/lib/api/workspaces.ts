import { apiRequest } from "@/lib/api/client";

export type WorkspaceStatus =
  | "pending"
  | "processing"
  | "needs_review"
  | "ready"
  | "failed";

export type DocumentStatus =
  | "uploaded"
  | "classifying"
  | "extracting"
  | "extracted"
  | "validated"
  | "failed";

export type FlagSeverity = "high" | "medium" | "low";
export type FlagStatus = "open" | "resolved" | "escalated";

export interface WorkspaceDocument {
  id: number;
  filename: string;
  doc_type: string | null;
  classification_confidence: string | null;
  status: DocumentStatus;
  error_message: string | null;
  extracted_data: Record<string, unknown> | null;
  upload_record_id: number | null;
  pipeline_run_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceFlag {
  id: number;
  flag_type: string;
  severity: FlagSeverity;
  title: string;
  detail: string;
  source_document_ids: number[];
  conflict_data: Record<string, unknown>;
  status: FlagStatus;
  resolved_by: string | null;
  resolved_at: string | null;
  resolution_note: string | null;
  resolution_value: string | null;
  created_at: string;
}

export interface Workspace {
  id: string;
  tenant_id: string;
  name: string;
  vertical_id: string;
  status: WorkspaceStatus;
  overall_confidence: string | null;
  pipeline_run_id: number | null;
  created_at: string;
  updated_at: string;
  // detail-only fields
  documents?: WorkspaceDocument[];
  flags?: WorkspaceFlag[];
  extracted_summary?: Record<string, unknown>;
  open_flag_count?: number;
  high_severity_count?: number;
}

export interface WorkspaceStatusPoll {
  workspace_id: string;
  status: WorkspaceStatus;
  overall_confidence: string | null;
  documents: Pick<WorkspaceDocument, "id" | "filename" | "doc_type" | "status" | "classification_confidence">[];
  open_flag_count: number;
  high_severity_count: number;
  flags: WorkspaceFlag[];
}

export async function createWorkspace(data: {
  name: string;
  vertical_id?: string;
  tenant_id?: string;
}): Promise<Workspace> {
  return apiRequest("/api/workspaces", {
    method: "POST",
    body: JSON.stringify({ vertical_id: "cre", tenant_id: "demo", ...data }),
  });
}

export async function listWorkspaces(tenantId = "demo"): Promise<Workspace[]> {
  return apiRequest(`/api/workspaces?tenant_id=${encodeURIComponent(tenantId)}`);
}

export async function getWorkspace(id: string): Promise<Workspace> {
  return apiRequest(`/api/workspaces/${id}`);
}

export async function registerDocument(
  workspaceId: string,
  filename: string,
  uploadRecordId?: number,
): Promise<WorkspaceDocument> {
  return apiRequest(`/api/workspaces/${workspaceId}/documents`, {
    method: "POST",
    body: JSON.stringify({ filename, upload_record_id: uploadRecordId ?? null }),
  });
}

export async function triggerProcessing(workspaceId: string) {
  return apiRequest(`/api/workspaces/${workspaceId}/process`, { method: "POST" });
}

export async function pollWorkspaceStatus(workspaceId: string): Promise<WorkspaceStatusPoll> {
  return apiRequest(`/api/workspaces/${workspaceId}/status`);
}

export async function resolveFlag(
  workspaceId: string,
  flagId: number,
  action: "resolve" | "escalate",
  opts?: { resolution_note?: string; resolution_value?: string; resolved_by?: string },
): Promise<WorkspaceFlag> {
  return apiRequest(`/api/workspaces/${workspaceId}/flags/${flagId}`, {
    method: "PATCH",
    body: JSON.stringify({ action, resolved_by: "operator", ...opts }),
  });
}
