import { AlertTriangle } from 'lucide-react';
import { subscriptionInfo } from '../../data/mockData';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

export function SubscriptionPanel() {
  const daysLeft = subscriptionInfo.daysRemaining;
  const isCritical = daysLeft <= 7;

  return (
    <div>
      <h3 className="text-[11px] font-semibold text-slate-500 dark:text-white/30 uppercase tracking-widest mb-3">Abonnement</h3>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] text-slate-400 dark:text-white/25 uppercase tracking-widest mb-0.5">Plan</p>
            <p className="text-[13px] font-semibold text-slate-800 dark:text-white/80">{subscriptionInfo.plan}</p>
          </div>
          <Badge variant="warning">{subscriptionInfo.status}</Badge>
        </div>

        <div className={`flex items-start gap-2 p-2.5 border ${isCritical ? 'bg-red-50 border-red-200 dark:bg-red-400/8 dark:border-red-400/20' : 'bg-amber-50 border-amber-200 dark:bg-amber-400/8 dark:border-amber-400/15'}`}>
          <AlertTriangle size={12} className={`mt-0.5 shrink-0 ${isCritical ? 'text-red-500' : 'text-amber-600 dark:text-amber-400'}`} />
          <p className={`text-[11px] font-medium ${isCritical ? 'text-red-700 dark:text-red-300' : 'text-amber-800 dark:text-amber-300'}`}>
            Nog <span className="font-bold">{daysLeft} dagen</span> gratis proberen.
          </p>
        </div>

        <div className="w-full bg-slate-100 dark:bg-white/[0.06] h-1 overflow-hidden">
          <div
            className={`h-full transition-all ${isCritical ? 'bg-red-500' : 'bg-amber-500'}`}
            style={{ width: `${((30 - daysLeft) / 30) * 100}%` }}
          />
        </div>

        <Button variant="secondary" size="sm" className="w-full justify-center">
          Beheer abonnement
        </Button>
      </div>
    </div>
  );
}
