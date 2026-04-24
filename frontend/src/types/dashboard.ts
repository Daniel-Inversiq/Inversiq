export type DashboardKpis = {
  sign_rate: number;
  pending_count: number;
};

export type RevenueSeriesItem = {
  label: string;
  value: number;
};

export type StatusDistributionItem = {
  label: string;
  value: number;
};

export type DashboardSummary = {
  kpis: DashboardKpis;
  revenue_series: RevenueSeriesItem[];
  status_distribution: StatusDistributionItem[];
};

export type ActivityItem = {
  id: string;
  event_type: string;
  title: string;
  link_url: string | null;
  created_at: string;
};

export type ActivityPayload = {
  items: ActivityItem[];
};
