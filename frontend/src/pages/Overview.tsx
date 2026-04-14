import { IntakeLink } from '../components/dashboard/IntakeLink';
import { TodayBanner } from '../components/dashboard/TodayBanner';
import { KPICards } from '../components/dashboard/KPICards';
import { RevenueChart } from '../components/dashboard/RevenueChart';
import { StatusDonut } from '../components/dashboard/StatusDonut';
import { FollowUpPanel } from '../components/dashboard/FollowUpPanel';
import { QuotesTable } from '../components/dashboard/QuotesTable';
import { Card } from '../components/ui/Card';
import { ArrowRight } from 'lucide-react';
import { kpiData, followUps } from '../data/mockData';

export function Overview({ onNavigate }: { onNavigate?: (id: string) => void }) {
  return (
    <div className="space-y-5 w-full">
      <IntakeLink onNavigate={onNavigate} />

      <TodayBanner openCount={kpiData.openOffertes} followUpCount={followUps.length} />

      <KPICards />

      <div className="grid grid-cols-[2fr_1fr] gap-4 items-start">
        <div className="space-y-4">
          <Card>
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="text-[15px] font-semibold text-neutral-950 dark:text-white/85 tracking-tight leading-none">Omzet & resultaten</h2>
                <p className="text-[11px] font-normal text-neutral-400 dark:text-white/25 mt-1">Afgelopen 6 maanden</p>
              </div>
              <div className="text-right">
                <p className="text-[22px] font-bold text-neutral-950 dark:text-white/85 tabular-nums leading-none tracking-tight">
                  € {kpiData.omzetMaand.toLocaleString('nl-NL')}
                </p>
                <p className="text-[11px] font-normal text-neutral-400 dark:text-white/25 mt-1">deze maand</p>
              </div>
            </div>
            <RevenueChart />
          </Card>

          <Card>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[15px] font-semibold text-neutral-950 dark:text-white/85 tracking-tight">Offertes die nog lopen</h2>
              <button className="flex items-center gap-1 text-[11px] font-medium text-neutral-400 hover:text-neutral-900 dark:text-white/25 dark:hover:text-white/60 transition-colors">
                Alle offertes
                <ArrowRight size={11} />
              </button>
            </div>
            <QuotesTable />
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <FollowUpPanel />
          </Card>
          <Card>
            <StatusDonut />
          </Card>
        </div>
      </div>
    </div>
  );
}
