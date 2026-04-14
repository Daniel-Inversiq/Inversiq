import { ArrowLeft, Clock, AlertTriangle, Eye } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';

type ReviewStatus = 'review_nodig' | 'goedgekeurd' | 'afgewezen';

interface ReviewItem {
  id: string;
  client: string;
  email: string;
  phone: string;
  timeAgo: string;
  type: string;
  status: ReviewStatus;
  reden: string | null;
}

const reviewData: ReviewItem[] = [
  {
    id: 'R-001',
    client: 'demo',
    email: 'demo@demo.nl',
    phone: '1232456',
    timeAgo: '1 min geleden',
    type: 'Paintly',
    status: 'review_nodig',
    reden: null,
  },
];

const statusConfig: Record<ReviewStatus, { label: string; className: string; icon: typeof AlertTriangle }> = {
  review_nodig: {
    label: 'Review nodig',
    className: 'bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-400/10 dark:text-amber-400 dark:ring-amber-400/20',
    icon: AlertTriangle,
  },
  goedgekeurd: {
    label: 'Goedgekeurd',
    className: 'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-400/10 dark:text-emerald-400 dark:ring-emerald-400/20',
    icon: Eye,
  },
  afgewezen: {
    label: 'Afgewezen',
    className: 'bg-red-50 text-red-700 ring-red-200 dark:bg-red-400/10 dark:text-red-400 dark:ring-red-400/20',
    icon: Eye,
  },
};

interface ReviewRowProps {
  item: ReviewItem;
  onNavigate?: (page: string) => void;
}

function ReviewRow({ item, onNavigate }: ReviewRowProps) {
  const cfg = statusConfig[item.status];
  const StatusIcon = cfg.icon;
  const initials = item.client.slice(0, 2).toUpperCase();

  return (
    <tr className="group border-b border-slate-100 dark:border-slate-700/60 last:border-0 hover:bg-slate-50/80 dark:hover:bg-slate-700/20 transition-colors">
      <td className="py-4 pr-6 pl-5">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-100 dark:bg-brand-400/15 text-brand-700 dark:text-brand-400 text-[11px] font-bold shrink-0">
            {initials}
          </div>
          <div className="min-w-0">
            <p className="text-[13px] font-semibold text-slate-800 dark:text-slate-100">{item.client}</p>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-[11px] text-slate-400 dark:text-slate-500">{item.email}</span>
              <span className="text-slate-300 dark:text-slate-600">·</span>
              <span className="text-[11px] text-slate-400 dark:text-slate-500">{item.phone}</span>
            </div>
            <div className="flex items-center gap-1 mt-1">
              <Clock size={10} className="text-slate-400 dark:text-slate-500" />
              <span className="text-[11px] text-slate-400 dark:text-slate-500">{item.timeAgo}</span>
            </div>
          </div>
        </div>
      </td>

      <td className="py-4 pr-6">
        <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold tracking-wide uppercase bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400 ring-1 ring-inset ring-slate-200 dark:ring-slate-600">
          {item.type}
        </span>
      </td>

      <td className="py-4 pr-6">
        <span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${cfg.className}`}>
          <StatusIcon size={11} />
          {cfg.label}
        </span>
      </td>

      <td className="py-4 pr-6">
        {item.reden ? (
          <p className="text-[13px] text-slate-600 dark:text-slate-400">{item.reden}</p>
        ) : (
          <span className="text-[12px] text-slate-400 dark:text-slate-500 italic">Geen reden opgegeven</span>
        )}
      </td>

      <td className="py-4 pr-5">
        <div className="flex items-center justify-end">
          <Button variant="primary" size="sm">
            <Eye size={12} />
            Controleer
          </Button>
        </div>
      </td>
    </tr>
  );
}

interface ReviewProps {
  onNavigate?: (page: string) => void;
}

export function Review({ onNavigate }: ReviewProps) {
  const pendingCount = reviewData.filter(r => r.status === 'review_nodig').length;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100 tracking-tight">
            Offertes die controle nodig hebben
          </h1>
          <p className="text-[13px] text-slate-500 dark:text-slate-400 mt-0.5">
            {pendingCount} {pendingCount === 1 ? 'offerte wacht' : 'offertes wachten'} op controle
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => onNavigate?.('offertes')}>
          <ArrowLeft size={13} />
          Terug naar offertes
        </Button>
      </div>

      {pendingCount > 0 && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-amber-50 dark:bg-amber-400/8 border border-amber-200 dark:border-amber-400/20">
          <AlertTriangle size={15} className="text-amber-600 dark:text-amber-400 shrink-0" />
          <p className="text-[13px] font-medium text-amber-700 dark:text-amber-400">
            {pendingCount} {pendingCount === 1 ? 'offerte vereist' : 'offertes vereisen'} jouw aandacht voordat {pendingCount === 1 ? 'deze verstuurd kan' : 'ze verstuurd kunnen'} worden.
          </p>
        </div>
      )}

      <Card noPadding>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-100 dark:border-slate-700/60">
                <th className="py-3 pl-5 pr-6 text-left text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide">Klant</th>
                <th className="py-3 pr-6 text-left text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide">Type</th>
                <th className="py-3 pr-6 text-left text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide">Status</th>
                <th className="py-3 pr-6 text-left text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide">Reden</th>
                <th className="py-3 pr-5 text-right text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide">Actie</th>
              </tr>
            </thead>
            <tbody>
              {reviewData.length > 0 ? (
                reviewData.map(item => (
                  <ReviewRow key={item.id} item={item} onNavigate={onNavigate} />
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="py-16 text-center">
                    <p className="text-sm font-medium text-slate-400 dark:text-slate-500">Geen offertes in review</p>
                    <p className="text-xs text-slate-400 dark:text-slate-600 mt-1">Alle offertes zijn gecontroleerd</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {reviewData.length > 0 && (
          <div className="px-5 py-3 border-t border-slate-100 dark:border-slate-700/60">
            <p className="text-[12px] text-slate-400 dark:text-slate-500">
              {reviewData.length} {reviewData.length === 1 ? 'offerte' : 'offertes'} in review
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}
