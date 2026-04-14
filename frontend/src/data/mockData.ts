import type { Quote, FollowUp, KPIData, RevenueDataPoint, OfferteFull, OffertesKPI } from '../types';

export const kpiData: KPIData = {
  omzetMaand: 625,
  offertesVerzonden: 1,
  akkoordPercentage: 100,
  openOffertes: 4,
  omzetDelta: 12.5,
  offertesDelta: 0,
};

export const revenueData: RevenueDataPoint[] = [
  { month: 'nov 2025', value: 0 },
  { month: 'dec 2025', value: 0 },
  { month: 'jan 2026', value: 0 },
  { month: 'feb 2026', value: 0 },
  { month: 'mrt 2026', value: 125 },
  { month: 'apr 2026', value: 625 },
];

export const statusData = {
  akkoord: 1,
  open: 4,
  verloren: 0,
  wordtVoorbereid: 2,
};

export const followUps: FollowUp[] = [
  {
    id: '1',
    clientName: 'Jan',
    description: 'Bel woensdag voor herstelwerkzaamheden',
    dateTime: 'Apr 15, 2026 · 12:00',
    priority: 'high',
  },
  {
    id: '2',
    clientName: 'De Vries Vastgoed',
    description: 'Offerte bespreken na bezichtiging',
    dateTime: 'Apr 17, 2026 · 09:30',
    priority: 'medium',
  },
  {
    id: '3',
    clientName: 'Pietersen',
    description: 'Nabellen over schilderwerk buitengevel',
    dateTime: 'Apr 19, 2026 · 14:00',
    priority: 'low',
  },
];

export const quotes: Quote[] = [
  {
    id: 'Q-001',
    client: 'Johan',
    amount: 1375,
    status: 'wordt_voorbereid',
    date: '2026-04-10',
    description: 'Buitenschilderwerk woonhuis',
  },
  {
    id: 'Q-002',
    client: 'De Vries Vastgoed',
    amount: 3200,
    status: 'open',
    date: '2026-04-08',
    description: 'Renovatie appartementencomplex',
  },
  {
    id: 'Q-003',
    client: 'Bakker & Zn.',
    amount: 890,
    status: 'open',
    date: '2026-04-05',
    description: 'Binnenschilderwerk kantoor',
  },
  {
    id: 'Q-004',
    client: 'Pietersen',
    amount: 560,
    status: 'akkoord',
    date: '2026-04-02',
    description: 'Gevelschilderwerk',
  },
  {
    id: 'Q-005',
    client: 'Hendriks Woning',
    amount: 2100,
    status: 'open',
    date: '2026-03-28',
    description: 'Compleet schilderwerk nieuwbouw',
  },
];

export const offertesKPI: OffertesKPI = {
  inBeeld: 5,
  directOpvolgen: 0,
  nogOpen: 0,
  binnen: 1,
};

export const offertesData: OfferteFull[] = [
  {
    id: 'OF-001',
    client: 'Johan',
    workflow: 'Paintly',
    amount: null,
    workflowStatus: 'bezig',
    documentStatus: 'offerte_gereed',
    followUp: null,
    date: '2026-04-10',
  },
  {
    id: 'OF-002',
    client: 'Kees',
    workflow: 'Paintly',
    amount: null,
    workflowStatus: 'bezig',
    documentStatus: 'offerte_gereed',
    followUp: null,
    date: '2026-04-09',
  },
  {
    id: 'OF-003',
    client: 'Marieke',
    workflow: 'Paintly',
    amount: null,
    workflowStatus: 'bezig',
    documentStatus: 'offerte_gereed',
    followUp: null,
    date: '2026-04-08',
  },
  {
    id: 'OF-004',
    client: 'Jan',
    workflow: 'Paintly',
    amount: null,
    workflowStatus: 'bezig',
    documentStatus: 'offerte_gereed',
    followUp: null,
    date: '2026-04-07',
  },
  {
    id: 'OF-005',
    client: 'Daniel van Lieshout',
    workflow: 'Paintly',
    amount: 1375,
    workflowStatus: 'verstuurd',
    documentStatus: 'geaccepteerd',
    followUp: null,
    date: '2026-04-02',
  },
];

export const intakeUrl = 'http://127.0.0.1:8000/intake/snoopy-schilderwerken';

export const workspaceName = 'Snoopy schilderwerken';

export const subscriptionInfo = {
  plan: 'Core',
  status: 'Proefperiode',
  daysRemaining: 13,
};
