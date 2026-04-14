import { TrendingUp, Send, CheckCircle2, Clock } from 'lucide-react';
import { kpiData } from '../../data/mockData';

interface KPICardProps {
  label: string;
  value: string;
  subtext?: string;
  delta?: number;
  icon: React.ComponentType<{ size?: number; className?: string }>;
}

function KPICard({ label, value, subtext, delta, icon: Icon }: KPICardProps) {
  return (
    <div className="bg-white dark:bg-white/[0.03] border border-neutral-200/90 dark:border-white/[0.07] shadow-none rounded-xl p-5 flex flex-col gap-3 min-h-[128px]">
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-semibold text-neutral-400 dark:text-white/30 tracking-[0.12em] uppercase">{label}</p>
        <Icon size={13} className="text-neutral-300 dark:text-white/15" strokeWidth={1.5} />
      </div>
      <div>
        <p className="text-[30px] font-bold text-neutral-950 dark:text-white/90 tracking-tight leading-none tabular-nums">{value}</p>
        {(subtext || delta !== undefined) && (
          <div className="mt-1.5 flex items-center gap-2">
            {delta !== undefined && (
              <span className={`inline-flex items-center gap-0.5 text-[11px] font-semibold ${delta >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500 dark:text-red-400'}`}>
                <TrendingUp size={10} className={delta < 0 ? 'rotate-180' : ''} />
                {delta >= 0 ? '+' : ''}{delta}%
              </span>
            )}
            {subtext && <span className="text-[11px] font-normal text-neutral-400 dark:text-white/20">{subtext}</span>}
          </div>
        )}
      </div>
    </div>
  );
}

export function KPICards() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <KPICard
        label="Omzet maand"
        value={`€ ${kpiData.omzetMaand.toLocaleString('nl-NL')}`}
        delta={kpiData.omzetDelta}
        subtext="vs vorige maand"
        icon={TrendingUp}
      />
      <KPICard
        label="Offertes verzonden"
        value={String(kpiData.offertesVerzonden)}
        subtext="deze maand"
        icon={Send}
      />
      <KPICard
        label="Akkoord %"
        value={`${kpiData.akkoordPercentage}%`}
        subtext="conversieratio"
        icon={CheckCircle2}
      />
      <KPICard
        label="Open offertes"
        value={String(kpiData.openOffertes)}
        subtext="wachten op reactie"
        icon={Clock}
      />
    </div>
  );
}
