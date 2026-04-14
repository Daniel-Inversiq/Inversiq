import { ArrowRight } from 'lucide-react';
import { followUps } from '../../data/mockData';
import type { FollowUp } from '../../types';

const priorityColor: Record<FollowUp['priority'], string> = {
  high: 'bg-red-500',
  medium: 'bg-amber-400',
  low: 'bg-neutral-300 dark:bg-white/20',
};

interface FollowUpItemProps {
  followUp: FollowUp;
}

function FollowUpItem({ followUp }: FollowUpItemProps) {
  return (
    <div className="flex gap-2.5 py-2.5 border-b border-neutral-100 dark:border-white/[0.05] last:border-0">
      <div className={`mt-[5px] w-1.5 h-1.5 rounded-full shrink-0 ${priorityColor[followUp.priority]}`} />
      <div className="flex-1 min-w-0">
        <p className="text-[12px] font-semibold text-neutral-900 dark:text-white/80 leading-snug">{followUp.clientName}</p>
        <p className="text-[11px] font-normal text-neutral-500 dark:text-white/30 mt-0.5 line-clamp-1 leading-snug">{followUp.description}</p>
        <p className="text-[10px] font-normal text-neutral-400 dark:text-white/20 mt-0.5 tabular-nums">{followUp.dateTime}</p>
      </div>
    </div>
  );
}

export function FollowUpPanel() {
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[10px] font-semibold text-neutral-400 dark:text-white/25 uppercase tracking-[0.12em]">Opvolging</h3>
        <button className="flex items-center gap-1 text-[11px] font-medium text-neutral-400 hover:text-neutral-900 dark:text-white/25 dark:hover:text-white/60 transition-colors">
          Alles
          <ArrowRight size={10} />
        </button>
      </div>
      <div>
        {followUps.map(fu => (
          <FollowUpItem key={fu.id} followUp={fu} />
        ))}
      </div>
    </div>
  );
}
