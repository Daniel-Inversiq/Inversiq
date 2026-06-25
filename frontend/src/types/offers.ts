export type PipelineRunItem = {
  id: number;
  tenant_id: string;
  lead_id: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
  submitted_at?: string | null;
  next_action_at?: string | null;
  review_created_at?: string | null;
  review_updated_at?: string | null;
};

export type PipelineRunsResponse = {
  total: number;
  items: PipelineRunItem[];
};

export type PipelineRunDebugResponse = {
  run: {
    id: number;
    tenant_id: string;
    lead_id: string;
    status: string;
    failure_step: string | null;
    error_category: string | null;
    overall_confidence_label: string | null;
    created_at: string | null;
    updated_at: string | null;
    completed_at: string | null;
  };
  summary: {
    total_steps: number;
    completed_steps: number;
    failed_steps: number;
    skipped_steps: number;
    event_count: number;
    recoverability: string;
    review_recommended: boolean;
    review_priority: string | null;
  };
};

export type QuoteTotalsPayload = {
  lead_id?: string;
  customer_name?: string;
  contact_name?: string;
  full_name?: string;
  name?: string;
  meta?: {
    lead_id?: string;
  };
  lead?: {
    id?: string;
    customer_name?: string;
    contact_name?: string;
    full_name?: string;
    name?: string;
  };
  request?: {
    lead_id?: string;
    customer_name?: string;
    contact_name?: string;
    full_name?: string;
    name?: string;
  };
  totals?: {
    grand_total?: number;
    pre_tax?: number;
  };
  project?: {
    description?: string;
    address?: string;
    location?: string;
  };
  summary?: {
    description?: string;
    address?: string;
    location?: string;
    project_description?: string;
    customer_name?: string;
    contact_name?: string;
    full_name?: string;
    name?: string;
  };
  intake?: {
    project_description?: string;
    address?: string;
    city?: string;
    street?: string;
    customer_name?: string;
    contact_name?: string;
    full_name?: string;
    name?: string;
  };
  /** Merged by GET /quotes/{id}/json from current tenant pricing (not frozen estimate meta). */
  quote_readiness?: {
    isReady?: boolean;
    missingConfig?: string[];
    missing_pricing_config?: boolean;
  };
  /** Persisted Lead.status for SPA actions (e.g. recalculate after CONFIG_NEEDED). */
  lead_status?: string;
};

export type TenantLeadListItem = {
  id: string;
  status: string;
  email: string;
  name: string;
  created_at?: string | null;
  updated_at?: string | null;
  submitted_at?: string | null;
  next_action_at?: string | null;
  review_created_at?: string | null;
  review_updated_at?: string | null;
};

export type OfferRow = {
  runId: number;
  leadId: string;
  customerName: string;
  projectDescription: string | null;
  status: string;
  createdAt: string | null;
  updatedAt: string | null;
  amount: number | null;
  amountLoadFailed: boolean;
  detailHref: string;
};

/** Dashboard / review queue: run-backed rows plus lead-only rows when no pipeline run exists. */
export type ReviewQueueRow = {
  /** Pipeline run id; 0 when only `Lead` carries review-needed status (no run). */
  runId: number;
  leadId: string;
  tenantId: string;
  status: string;
  createdAt: string | null;
  updatedAt: string | null;
  customerName: string;
  /** Primary review workspace route (`/reviews/{leadId}`). */
  primaryHref: string;
  /** Set by operational dashboard API for prioritisation hints. */
  urgencyScore?: number;
};
