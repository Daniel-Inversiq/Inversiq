export type SectorDashboardMetrics = {
  leadsCount: number;
  openQuotesCount: number;
  activeJobsCount: number;
  reviewCount: number;
  urgentReviewCount: number;
  midUrgencyReviewCount: number;
  scheduledTodayCount: number;
  hasPipelineValue: boolean;
  pipelineValueTotal: number;
  intakeRangeDays: 7 | 14 | 30 | 90;
  statusDistribution: [string, number][];
};

export type SectorDashboardComponentProps = {
  metrics: SectorDashboardMetrics;
};
