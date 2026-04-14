import { ExternalLink, RefreshCw, FileText } from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';
import { getOffertes } from '../../services/offertes';
import type { OfferteListItem } from '../../services/offertes';
import { StatusBadge } from '../ui/Badge';

export function QuotesTable() {
  const [quotes, setQuotes] = useState<OfferteListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<boolean>(false);

  const loadOffertes = useCallback(async (signal: AbortSignal) => {
    setLoading(true);
    setError(false);
    try {
      const data = await getOffertes();
      if (!signal.aborted) setQuotes(data);
    } catch {
      if (!signal.aborted) setError(true);
    } finally {
      if (!signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadOffertes(controller.signal);
    return () => controller.abort();
  }, [loadOffertes]);

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b border-neutral-200 dark:border-white/[0.07]">
            <th className="pb-2 pr-3 text-left text-[9px] font-semibold text-neutral-500 dark:text-white/25 uppercase tracking-[0.12em]">Klant</th>
            <th className="pb-2 pr-3 text-left text-[9px] font-semibold text-neutral-500 dark:text-white/25 uppercase tracking-[0.12em]">Omschrijving</th>
            <th className="pb-2 pr-3 text-right text-[9px] font-semibold text-neutral-500 dark:text-white/25 uppercase tracking-[0.12em]">Bedrag</th>
            <th className="pb-2 pr-3 text-left text-[9px] font-semibold text-neutral-500 dark:text-white/25 uppercase tracking-[0.12em]">Status</th>
            <th className="pb-2 text-right text-[9px] font-semibold text-neutral-500 dark:text-white/25 uppercase tracking-[0.12em]">Actie</th>
          </tr>
        </thead>
        <tbody>
          {loading && (
            <tr className="border-0">
              <td colSpan={5}>
                <div className="flex items-center gap-2 py-6 text-[11px] text-slate-400 dark:text-white/25">
                  <RefreshCw size={12} className="animate-spin" />
                  Offertes laden…
                </div>
              </td>
            </tr>
          )}
          {!loading && error && (
            <tr className="border-0">
              <td colSpan={5}>
                <div className="flex flex-col items-center gap-2 py-8 text-center">
                  <FileText size={22} className="text-slate-200 dark:text-white/10" />
                  <p className="text-[12px] font-medium text-slate-400 dark:text-white/25">Offertes niet beschikbaar</p>
                  <button
                    onClick={() => void loadOffertes(new AbortController().signal)}
                    className="mt-1 flex items-center gap-1.5 text-[11px] font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400 transition-colors"
                  >
                    <RefreshCw size={11} />
                    Opnieuw proberen
                  </button>
                </div>
              </td>
            </tr>
          )}
          {!loading && !error && quotes.length === 0 && (
            <tr className="border-0">
              <td colSpan={5}>
                <div className="flex flex-col items-center gap-1.5 py-8 text-center">
                  <FileText size={22} className="text-slate-200 dark:text-white/10" />
                  <p className="text-[12px] font-medium text-slate-400 dark:text-white/25">Geen open offertes</p>
                </div>
              </td>
            </tr>
          )}
          {quotes.map((quote, i) => (
            <tr
              key={quote.id}
              className={`group border-b dark:border-white/[0.05] hover:bg-slate-50 dark:hover:bg-white/[0.02] transition-colors ${i === quotes.length - 1 ? 'border-0' : 'border-slate-100'}`}
            >
              <td className="py-2 pr-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-5 h-5 bg-slate-100 dark:bg-white/[0.06] text-slate-600 dark:text-white/50 text-[9px] font-bold shrink-0 rounded-sm">
                    {quote.client.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <p className="text-[12px] font-semibold text-slate-900 dark:text-white/85 leading-snug">{quote.client}</p>
                    <p className="text-[10px] font-normal text-slate-400 dark:text-white/25 leading-none mt-0.5">{quote.id}</p>
                  </div>
                </div>
              </td>
              <td className="py-2 pr-3">
                <p className="text-[11px] font-normal text-slate-500 dark:text-white/40 max-w-[180px] truncate">{quote.description}</p>
              </td>
              <td className="py-2 pr-3 text-right">
                <p className="text-[13px] font-bold text-slate-900 dark:text-white/85 tabular-nums">
                  € {quote.amount.toLocaleString('nl-NL', { minimumFractionDigits: 2 })}
                </p>
              </td>
              <td className="py-1.5 pr-3">
                <StatusBadge status={quote.status} />
              </td>
              <td className="py-1.5 text-right">
                <button className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-400 hover:text-slate-700 dark:text-white/25 dark:hover:text-white/60 opacity-0 group-hover:opacity-100 transition-all">
                  Bekijk
                  <ExternalLink size={10} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
