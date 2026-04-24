export type JobListItem = {
  id: number;
  tenant_id: string;
  lead_id: string;
  lead_name: string | null;
  status: string;
  scheduled_at: string | null;
  scheduled_tz: string | null;
  started_at: string | null;
  done_at: string | null;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
};
