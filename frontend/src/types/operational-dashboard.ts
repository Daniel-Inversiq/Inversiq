/** Response from `GET /app/api/dashboard/operational`. */

export type OperationalKpiBlock = {
  value: number;
  inflow_last_7d?: number;
  inflow_prev_7d?: number;
  inflow_delta?: number;
  touched_last_7d?: number;
  touched_prev_7d?: number;
  touched_delta?: number;
  updated_last_7d?: number;
  updated_prev_7d?: number;
  updated_delta?: number;
  high_urgency?: number;
};

export type OperationalDashboardKpis = {
  new_requests: OperationalKpiBlock;
  open_quotes: OperationalKpiBlock;
  active_jobs: OperationalKpiBlock;
  review_queue: OperationalKpiBlock;
};

export type IntakeSeriesPointApi = {
  day_key: string;
  count: number;
};

export type IntakeChartSummaryApi = {
  total: number;
  avg_per_day: number;
  zero_day_count: number;
  peak_day_key: string;
  peak_count: number;
  prior_range_total: number;
  prior_range_days: number;
};

export type OperationalAttentionItemApi = {
  run_id: number;
  lead_id: string;
  tenant_id: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
  customer_name: string;
  primary_href: string;
  urgency_score: number;
};

export type OperationalDashboardResponse = {
  generated_at: string | null;
  timezone_offset_minutes: number;
  kpis: OperationalDashboardKpis;
  intake: {
    range_days: number;
    series: IntakeSeriesPointApi[];
    summary: IntakeChartSummaryApi;
  };
  status_distribution: [string, number][];
  attention: {
    items: OperationalAttentionItemApi[];
    summary: {
      total: number;
      high_urgency: number;
      shown: number;
    };
  };
  activity_strip: {
    pipeline_runs_in_view: number;
    scheduled_jobs: number;
  };
  outcomes: {
    range_days: number;
    total_requests: number;
    accepted_count: number;
    rejected_count: number;
    decided_count: number;
    accepted_rate: number;
    rejected_rate: number;
  };
  meta: {
    leads_limit: number;
    jobs_limit: number;
    pipeline_runs_limit: number;
  };
};
