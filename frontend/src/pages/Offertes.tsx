import { useEffect, useMemo, useState } from 'react';
import { Plus, Search, RotateCcw, Eye, Link2, User, ChevronDown } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import type { OfferteFull, WorkflowStatus, DocumentStatus } from '../types';
import { OfferteDetail } from '../components/offertes/OfferteDetail';
import { getOffertes } from '../services/offertes';
import type { OfferteListItem } from '../services/offertes';

const workflowStatusConfig: Record<WorkflowStatus, { label: string; className: string }> = {
  bezig: {
    label: 'Bezig',
    className: 'bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-400/10 dark:text-amber-400 dark:ring-amber-400/20',
  },
  wacht_op_klant: {
    label: 'Wacht op klant',
    className: 'bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-400/10 dark:text-blue-400 dark:ring-blue-400/20',
  },
  verstuurd: {
    label: 'Verstuurd',
    className: 'bg-slate-100 text-slate-600 ring-slate-200 dark:bg-slate-700/40 dark:text-slate-300 dark:ring-slate-600',
  },
};

const documentStatusConfig: Record<DocumentStatus, { label: string; className: string }> = {
  concept: {
    label: 'Concept',
    className: 'bg-slate-100 text-slate-600 ring-slate-200 dark:bg-slate-700/40 dark:text-slate-300 dark:ring-slate-600',
  },
  offerte_gereed: {
    label: 'Offerte gereed',
    className: 'bg-cyan-50 text-cyan-700 ring-cyan-200 dark:bg-cyan-400/10 dark:text-cyan-400 dark:ring-cyan-400/20',
  },
  verzonden: {
    label: 'Verzonden',
    className: 'bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-400/10 dark:text-blue-400 dark:ring-blue-400/20',
  },
  geaccepteerd: {
    label: 'Geaccepteerd',
    className: 'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-400/10 dark:text-emerald-400 dark:ring-emerald-400/20',
  },
};

function StatusPill({ className, label }: { className: string; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${className}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-60" />
      {label}
    </span>
  );
}

interface SelectProps {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}

function FilterSelect({ value, onChange, options }: SelectProps) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="appearance-none h-9 pl-3 pr-8 text-[13px] font-medium text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-lg shadow-card focus:outline-none focus:ring-2 focus:ring-brand-500 cursor-pointer transition-colors hover:border-slate-300 dark:hover:border-slate-600"
      >
        {options.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <ChevronDown size={13} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: number;
  sub: string;
  accent?: boolean;
}

function StatCard({ label, value, sub, accent }: StatCardProps) {
  return (
    <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/60 shadow-card p-5">
      <p className="text-[10px] font-semibold tracking-widest uppercase text-slate-400 dark:text-slate-500 mb-3">{label}</p>
      <p className={`text-3xl font-bold tracking-tight leading-none ${accent ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-900 dark:text-slate-100'}`}>
        {value}
      </p>
      <p className="text-xs text-slate-500 dark:text-slate-400 mt-1.5">{sub}</p>
    </div>
  );
}

interface OfferteRowProps {
  offerte: OfferteFull;
  onSelect: (o: OfferteFull) => void;
}

function OfferteRow({ offerte, onSelect }: OfferteRowProps) {
  const wfConfig = workflowStatusConfig[offerte.workflowStatus];
  const docConfig = documentStatusConfig[offerte.documentStatus];
  const initials = offerte.client.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();

  return (
    <tr onClick={() => onSelect(offerte)} className="group border-b border-slate-100 dark:border-slate-700/60 last:border-0 hover:bg-slate-50/80 dark:hover:bg-slate-700/20 transition-colors cursor-pointer">
      <td className="py-4 pr-6 pl-5">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-100 dark:bg-brand-400/15 text-brand-700 dark:text-brand-400 text-[11px] font-bold shrink-0">
            {initials}
          </div>
          <div className="min-w-0">
            <p className="text-[13px] font-semibold text-slate-800 dark:text-slate-100">{offerte.client}</p>
            <div className="flex items-center gap-2 mt-1">
              <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold tracking-wide uppercase bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400 ring-1 ring-inset ring-slate-200 dark:ring-slate-600">
                {offerte.workflow}
              </span>
              <span className="text-[11px] text-slate-400 dark:text-slate-500">
                {offerte.amount != null
                  ? `€ ${offerte.amount.toLocaleString('nl-NL', { minimumFractionDigits: 2 })}`
                  : 'Offertebedrag nog niet bekend'}
              </span>
            </div>
          </div>
        </div>
      </td>

      <td className="py-4 pr-6">
        <div className="flex flex-wrap gap-1.5">
          <StatusPill label={wfConfig.label} className={wfConfig.className} />
          <StatusPill label={docConfig.label} className={docConfig.className} />
        </div>
      </td>

      <td className="py-4 pr-6">
        {offerte.followUp ? (
          <p className="text-[13px] text-slate-600 dark:text-slate-400">{offerte.followUp}</p>
        ) : (
          <span className="inline-flex items-center rounded-md px-2 py-1 text-xs font-medium text-slate-400 dark:text-slate-500 ring-1 ring-inset ring-slate-200 dark:ring-slate-700/60">
            Geen opvolging gepland
          </span>
        )}
      </td>

      <td className="py-4 pr-5">
        <div className="flex items-center justify-end gap-1.5" onClick={e => e.stopPropagation()}>
          <Button variant="primary" size="sm" onClick={() => onSelect(offerte)}>
            <Eye size={12} />
            Bekijk offerte
          </Button>
          <Button variant="secondary" size="sm">
            <User size={12} />
            Klantlink
          </Button>
          <Button variant="ghost" size="sm" className="px-2">
            <Link2 size={13} />
          </Button>
        </div>
      </td>
    </tr>
  );
}

export function Offertes() {
  const [selectedOfferte, setSelectedOfferte] = useState<OfferteFull | null>(null);
  const [offertes, setOffertes] = useState<OfferteFull[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('alle');
  const [urgentieFilter, setUrgentieFilter] = useState('alle');
  const [workflowFilter, setWorkflowFilter] = useState('alle');

  useEffect(() => {
    let isMounted = true;

    const toOfferteFull = (item: OfferteListItem): OfferteFull => {
      const statusToDocument: Record<OfferteListItem['status'], DocumentStatus> = {
        wordt_voorbereid: 'offerte_gereed',
        open: 'verzonden',
        akkoord: 'geaccepteerd',
        verloren: 'concept',
      };
      const statusToWorkflow: Record<OfferteListItem['status'], WorkflowStatus> = {
        wordt_voorbereid: 'bezig',
        open: 'wacht_op_klant',
        akkoord: 'verstuurd',
        verloren: 'verstuurd',
      };

      return {
        id: item.id,
        client: item.client,
        workflow: 'Paintly',
        amount: item.amount,
        workflowStatus: statusToWorkflow[item.status],
        documentStatus: statusToDocument[item.status],
        followUp: null,
        date: '',
      };
    };

    const loadOffertes = async () => {
      setLoading(true);
      setError(null);
      try {
        const apiItems = await getOffertes();
        if (isMounted) {
          setOffertes(apiItems.map(toOfferteFull));
        }
      } catch (err: unknown) {
        if (isMounted) {
          const message = err instanceof Error ? err.message : 'Er is een fout opgetreden';
          setError(message);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    void loadOffertes();

    return () => {
      isMounted = false;
    };
  }, []);

  const filtered = useMemo(() => {
    return offertes.filter(o => {
      const matchSearch = search === '' || o.client.toLowerCase().includes(search.toLowerCase());
      const matchStatus = statusFilter === 'alle' || o.documentStatus === statusFilter;
      const matchWorkflow = workflowFilter === 'alle' || o.workflow.toLowerCase() === workflowFilter.toLowerCase();
      return matchSearch && matchStatus && matchWorkflow;
    });
  }, [offertes, search, statusFilter, urgentieFilter, workflowFilter]);

  if (selectedOfferte) {
    return <OfferteDetail offerte={selectedOfferte} onBack={() => setSelectedOfferte(null)} />;
  }

  const handleReset = () => {
    setSearch('');
    setStatusFilter('alle');
    setUrgentieFilter('alle');
    setWorkflowFilter('alle');
  };

  const totalCount = offertes.length;
  const teLaatCount = 0;
  const geaccepteerdCount = offertes.filter(o => o.documentStatus === 'geaccepteerd').length;
  const offertesKPI = {
    inBeeld: totalCount,
    directOpvolgen: teLaatCount,
    nogOpen: offertes.filter(o => o.documentStatus === 'verzonden' || o.documentStatus === 'offerte_gereed').length,
    binnen: geaccepteerdCount,
  };

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100 tracking-tight">Offertes</h1>
          <p className="text-[13px] text-slate-500 dark:text-slate-400 mt-0.5">
            {totalCount} offertes · {teLaatCount} te laat · {geaccepteerdCount} geaccepteerd
          </p>
        </div>
        <Button variant="primary" size="md">
          <Plus size={14} />
          Nieuwe offerte
        </Button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="In beeld" value={offertesKPI.inBeeld} sub="Offertes" />
        <StatCard label="Direct opvolgen" value={offertesKPI.directOpvolgen} sub="Te laat" />
        <StatCard label="Nog open" value={offertesKPI.nogOpen} sub="Verstuurd / bekeken" />
        <StatCard label="Binnen" value={offertesKPI.binnen} sub="Geaccepteerd" accent />
      </div>

      <Card noPadding>
        <div className="p-5 border-b border-slate-100 dark:border-slate-700/60">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Je offertes</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Filter en pak sneller door</p>
        </div>

        <div className="px-5 py-3.5 border-b border-slate-100 dark:border-slate-700/60 flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[200px]">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500 pointer-events-none" />
            <input
              type="text"
              placeholder="Zoek op klant..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full h-9 pl-9 pr-3 text-[13px] text-slate-800 dark:text-slate-200 bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-lg shadow-card placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500 transition-colors"
            />
          </div>

          <FilterSelect
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: 'alle', label: 'Alle standen' },
              { value: 'offerte_gereed', label: 'Offerte gereed' },
              { value: 'geaccepteerd', label: 'Geaccepteerd' },
              { value: 'verzonden', label: 'Verzonden' },
              { value: 'concept', label: 'Concept' },
            ]}
          />

          <FilterSelect
            value={urgentieFilter}
            onChange={setUrgentieFilter}
            options={[
              { value: 'alle', label: 'Alle urgentie' },
              { value: 'hoog', label: 'Hoog' },
              { value: 'normaal', label: 'Normaal' },
              { value: 'laag', label: 'Laag' },
            ]}
          />

          <FilterSelect
            value={workflowFilter}
            onChange={setWorkflowFilter}
            options={[
              { value: 'alle', label: 'Alle workflows' },
              { value: 'paintly', label: 'Paintly' },
            ]}
          />

          <button
            onClick={handleReset}
            className="h-9 px-3 flex items-center gap-1.5 text-[13px] font-medium text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700/40 rounded-lg transition-colors"
          >
            <RotateCcw size={13} />
            Reset
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-100 dark:border-slate-700/60">
                <th className="py-3 pl-5 pr-6 text-left text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide">Klant</th>
                <th className="py-3 pr-6 text-left text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide">Status</th>
                <th className="py-3 pr-6 text-left text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide">Opvolging</th>
                <th className="py-3 pr-5 text-right text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide">Acties</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={4} className="py-16 text-center">
                    <p className="text-sm font-medium text-slate-400 dark:text-slate-500">Laden...</p>
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan={4} className="py-16 text-center">
                    <p className="text-sm font-medium text-slate-400 dark:text-slate-500">{error}</p>
                  </td>
                </tr>
              ) : filtered.length > 0 ? (
                filtered.map(o => <OfferteRow key={o.id} offerte={o} onSelect={setSelectedOfferte} />)
              ) : (
                <tr>
                  <td colSpan={4} className="py-16 text-center">
                    <p className="text-sm font-medium text-slate-400 dark:text-slate-500">Geen offertes gevonden</p>
                    <p className="text-xs text-slate-400 dark:text-slate-600 mt-1">Pas je filters aan of maak een nieuwe offerte</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {filtered.length > 0 && (
          <div className="px-5 py-3 border-t border-slate-100 dark:border-slate-700/60 flex items-center justify-between">
            <p className="text-[12px] text-slate-400 dark:text-slate-500">
              {filtered.length} van {totalCount} offertes
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}
