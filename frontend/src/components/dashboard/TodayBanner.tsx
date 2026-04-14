import { FileText, ChevronRight } from 'lucide-react';
import { Button } from '../ui/Button';

interface TodayBannerProps {
  openCount: number;
  followUpCount: number;
}

export function TodayBanner({ openCount, followUpCount }: TodayBannerProps) {
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-3.5 bg-white dark:bg-white/[0.03] border border-neutral-200/90 dark:border-white/[0.07] rounded-xl shadow-none">
      <div className="flex items-center gap-3">
        <div className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
        <div>
          <p className="text-[14px] font-semibold text-neutral-900 dark:text-white/80 tracking-tight">Vandaag te regelen</p>
          <p className="text-[11px] text-neutral-500 dark:text-white/30 mt-1">
            <span className="text-neutral-900 dark:text-white/50 font-medium">{openCount} open offertes</span>
            {' · '}
            <span className="text-neutral-900 dark:text-white/50 font-medium">{followUpCount} aanvragen</span> om op te volgen
          </p>
        </div>
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        <Button variant="primary" size="sm">
          <FileText size={12} />
          Bekijk offertes
        </Button>
        <Button variant="secondary" size="sm">
          Opvolging
          <ChevronRight size={12} />
        </Button>
      </div>
    </div>
  );
}
