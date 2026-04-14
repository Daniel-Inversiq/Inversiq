export type QuoteStatus = 'wordt_voorbereid' | 'open' | 'akkoord' | 'verloren';

export interface Quote {
  id: string;
  client: string;
  amount: number;
  status: QuoteStatus;
  date: string;
  description: string;
}

export interface FollowUp {
  id: string;
  clientName: string;
  description: string;
  dateTime: string;
  priority: 'high' | 'medium' | 'low';
}

export interface KPIData {
  omzetMaand: number;
  offertesVerzonden: number;
  akkoordPercentage: number;
  openOffertes: number;
  omzetDelta: number;
  offertesDelta: number;
}

export interface RevenueDataPoint {
  month: string;
  value: number;
}

export interface NavItem {
  id: string;
  label: string;
  icon: string;
  href: string;
}

export type WorkflowStatus = 'bezig' | 'wacht_op_klant' | 'verstuurd';
export type DocumentStatus = 'offerte_gereed' | 'concept' | 'verzonden' | 'geaccepteerd';

export interface OfferteFull {
  id: string;
  client: string;
  workflow: string;
  amount: number | null;
  workflowStatus: WorkflowStatus;
  documentStatus: DocumentStatus;
  followUp: string | null;
  date: string;
}

export interface OffertesKPI {
  inBeeld: number;
  directOpvolgen: number;
  nogOpen: number;
  binnen: number;
}
