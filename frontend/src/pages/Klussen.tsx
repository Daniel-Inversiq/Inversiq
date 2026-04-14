import { useState, useMemo } from 'react';
import { Calendar, FileText, Mail, CheckCircle2, Eye } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';

type KlusStatus = 'nieuw' | 'ingepland' | 'bezig' | 'afgerond' | 'geannuleerd';

interface Klus {
  id: string;
  number: number;
  offerteRef: string;
  status: KlusStatus;
  client: string;
  email: string;
  wanneer: string | null;
}

const klussenData: Klus[] = [
  {
    id: 'K-001',
    number: 1,
    offerteRef: 'Offerte #E69C42',
    status: 'afgerond',
    client: 'Daniel van Lieshout',
    email: 'dvanlieshout00@gmail.com',
    wanneer: null,
  },
];

type FilterTab = KlusStatus | 'alles';

const tabs: { key: FilterTab; label: string }[] = [
  { key: 'alles', label: 'Alles' },
  { key: 'nieuw', label: 'Nieuw' },
  { key: 'ingepland', label: 'Ingepland' },
  { key: 'bezig', label: 'Bezig' },
  { key: 'afgerond', label: 'Afgerond' },
  { key: 'geannuleerd', label: 'Geannuleerd' },
];

const statusConfig: Record<KlusStatus, { label: string; dot: string; badge: string }> = {
  nieuw: {
    label: 'Nieuw',
    dot: 'bg-amber-400',
    badge: 'bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-400/10 dark:text-amber-400 dark:ring-amber-400/20',
  },
  ingepland: {
    label: 'Ingepland',
    dot: 'bg-blue-400',
    badge: 'bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-400/10 dark:text-blue-400 dark:ring-blue-400/20',
  },
  bezig: {
    label: 'Bezig',
    dot: 'bg-orange-400',
    badge: 'bg-orange-50 text-orange-700 ring-orange-200 dark:bg-orange-400/10 dark:text-orange-400 dark:ring-orange-400/20',
  },
  afgerond: {
    label: 'Afgerond',
    dot: 'bg-emerald-400',
    badge: 'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-400/10 dark:text-emerald-400 dark:ring-emerald-400/20',
  },
  geannuleerd: {
    label: 'Geannuleerd',
    dot: 'bg-slate-400',
    badge: 'bg-slate-100 text-slate-600 ring-slate-200 dark:bg-slate-700/40 dark:text-slate-400 dark:ring-slate-600',
  },
};

function countByStatus(status: KlusStatus) {
  return klussenData.filter(k => k.status === status).length;
}

interface KlusRowProps {
  klus: Klus;
}

function KlusRow({ klus }: KlusRowProps) {
  const cfg = statusConfig[klus.status];
  const initials = klus.client.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();

  return (
    <tr className="group border-b border-slate-100 dark:border-slate-700/60 last:border-0 hover:bg-slate-50/80 dark:hover:bg-slate-700/20 transition-colors">
      <td className="py-4 pr-6 pl-5">
        <p className="text-[13px] font-semibold text-slate-800 dark:text-slate-100">#{klus.number}</p>
        <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">{klus.offerteRef}</p>
      </td>

      <td className="py-4 pr-6">
        <span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${cfg.badge}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
          {cfg.label}
        </span>
      </td>

      <td className="py-4 pr-6">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-7 h-7 rounded-full bg-brand-100 dark:bg-brand-400/15 text-brand-700 dark:text-brand-400 text-[10px] font-bold shrink-0">
            {initials}
          </div>
          <div className="min-w-0">
            <p className="text-[13px] font-semibold text-slate-800 dark:text-slate-100">{klus.client}</p>
            <div className="flex items-center gap-1 mt-0.5">
              <Mail size={11} className="text-slate-400 dark:text-slate-500 shrink-0" />
              <p className="text-[11px] text-slate-400 dark:text-slate-500 truncate">{klus.email}</p>
            </div>
          </div>
        </div>
      </td>

      <td className="py-4 pr-6">
        {klus.wanneer ? (
          <div className="flex items-center gap-1.5 text-[13px] text-slate-600 dark:text-slate-400">
            <Calendar size={13} className="text-slate-400 dark:text-slate-500" />
            {klus.wanneer}
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            {klus.status === 'afgerond' ? (
              <div className="flex items-center gap-1.5 text-[13px] text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 size={14} />
                Afgerond
              </div>
            ) : (
              <span className="text-[12px] text-slate-400 dark:text-slate-500">—</span>
            )}
          </div>
        )}
      </td>

      <td className="py-4 pr-5">
        <div className="flex items-center justify-end opacity-0 group-hover:opacity-100 transition-opacity">
          <Button variant="secondary" size="sm">
            <Eye size={12} />
            Bekijk offerte
          </Button>
        </div>
      </td>
    </tr>
  );
}

export function Klussen() {
  const [activeTab, setActiveTab] = useState<FilterTab>('alles');

  const filtered = useMemo(() => {
    if (activeTab === 'alles') return klussenData;
    return klussenData.filter(k => k.status === activeTab);
  }, [activeTab]);

  const totalCount = klussenData.length;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100 tracking-tight">Klussenoverzicht</h1>
          <p className="text-[13px] text-slate-500 dark:text-slate-400 mt-0.5">
            {totalCount} {totalCount === 1 ? 'klus' : 'klussen'} · planning en overzicht
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm">
            <Calendar size={13} />
            Agenda
          </Button>
          <Button variant="primary" size="sm">
            <FileText size={13} />
            Offertes
          </Button>
        </div>
      </div>

      <Card noPadding>
        <div className="px-5 pt-4 pb-0 border-b border-slate-100 dark:border-slate-700/60">
          <div className="flex items-center gap-1 overflow-x-auto">
            {tabs.map(tab => {
              const count = tab.key === 'alles' ? totalCount : countByStatus(tab.key as KlusStatus);
              const isActive = activeTab === tab.key;
              const dotColor = tab.key !== 'alles' ? statusConfig[tab.key as KlusStatus].dot : '';

              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`relative flex items-center gap-2 px-3 py-2.5 text-[13px] font-medium rounded-t-md whitespace-nowrap transition-colors ${
                    isActive
                      ? 'text-slate-900 dark:text-slate-100 bg-transparent'
                      : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
                  }`}
                >
                  {tab.key !== 'alles' && (
                    <span className={`h-1.5 w-1.5 rounded-full ${dotColor} ${isActive ? 'opacity-100' : 'opacity-60'}`} />
                  )}
                  {tab.label}
                  <span className={`inline-flex items-center justify-center min-w-[18px] h-[18px] rounded-full text-[10px] font-semibold px-1 ${
                    isActive
                      ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                      : 'bg-slate-100 text-slate-500 dark:bg-slate-700/60 dark:text-slate-400'
                  }`}>
                    {count}
                  </span>
                  {isActive && (
                    <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-brand-500 rounded-t-full" />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-100 dark:border-slate-700/60">
                <th className="py-3 pl-5 pr-6 text-left text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide">Klus</th>
                <th className="py-3 pr-6 text-left text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide">Status</th>
                <th className="py-3 pr-6 text-left text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide">Klant</th>
                <th className="py-3 pr-6 text-left text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide">Wanneer</th>
                <th className="py-3 pr-5 text-right text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide">Actie</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length > 0 ? (
                filtered.map(k => <KlusRow key={k.id} klus={k} />)
              ) : (
                <tr>
                  <td colSpan={5} className="py-16 text-center">
                    <p className="text-sm font-medium text-slate-400 dark:text-slate-500">Geen klussen gevonden</p>
                    <p className="text-xs text-slate-400 dark:text-slate-600 mt-1">Er zijn nog geen klussen in deze categorie</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {filtered.length > 0 && (
          <div className="px-5 py-3 border-t border-slate-100 dark:border-slate-700/60">
            <p className="text-[12px] text-slate-400 dark:text-slate-500">
              {filtered.length} van {totalCount} {totalCount === 1 ? 'klus' : 'klussen'}
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}
