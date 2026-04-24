export type UploadListItem = {
  id: number;
  tenant_id: string;
  lead_id: string;
  lead_name: string | null;
  object_key: string;
  filename: string;
  status: string;
  mime: string;
  size: number;
  created_at: string | null;
  updated_at: string | null;
};
