import { useState } from 'react';
import { Copy, ExternalLink, MessageCircle, Check, Link, Plus } from 'lucide-react';
import { intakeUrl } from '../../data/mockData';

interface IntakeLinkProps {
  onNavigate?: (id: string) => void;
}

export function IntakeLink({ onNavigate }: IntakeLinkProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(intakeUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex items-center gap-3 px-4 py-3.5 bg-white dark:bg-white/[0.03] border border-neutral-200/90 dark:border-white/[0.07] rounded-xl shadow-none">
      <Link size={13} className="text-neutral-400 dark:text-white/25 shrink-0" strokeWidth={1.5} />
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-semibold tracking-widest uppercase text-neutral-400 dark:text-white/25 mb-0.5">
          Intake-link
        </p>
        <p className="text-[12px] text-neutral-600 dark:text-white/50 truncate font-mono">
          {intakeUrl}
        </p>
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <button
          onClick={() => onNavigate?.('intake')}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-semibold bg-neutral-950 text-white hover:bg-neutral-800 dark:bg-white/10 dark:text-white/80 dark:hover:bg-white/15 transition-colors rounded-md"
        >
          <Plus size={11} />
          Nieuwe intake
        </button>
        <button
          onClick={handleCopy}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-medium border transition-colors rounded ${
            copied
              ? 'border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-400/30 dark:bg-emerald-400/10 dark:text-emerald-400'
              : 'border-neutral-200 bg-white text-neutral-600 hover:bg-neutral-50 dark:border-white/10 dark:bg-white/[0.03] dark:text-white/40 dark:hover:bg-white/[0.06]'
          }`}
        >
          {copied ? <Check size={11} /> : <Copy size={11} />}
          {copied ? 'Gekopieerd' : 'Kopieer'}
        </button>
        <button className="flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-medium border border-neutral-200 bg-white text-neutral-600 hover:bg-neutral-50 dark:border-white/10 dark:bg-white/[0.03] dark:text-white/40 dark:hover:bg-white/[0.06] transition-colors rounded-md">
          <ExternalLink size={11} />
          Open
        </button>
        <button className="flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-medium bg-emerald-700 text-white hover:bg-emerald-800 transition-colors rounded">
          <MessageCircle size={11} />
          WhatsApp
        </button>
      </div>
    </div>
  );
}
