import { useState } from 'react';
import {
  ArrowLeft, ExternalLink, Download, Pencil, AlertTriangle,
  User, Mail, Phone, MapPin, Layers, Wrench, Hash, Clock,
  Calendar, StickyNote, CheckCircle2, Image as ImageIcon, ChevronRight,
} from 'lucide-react';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { OfferteEdit } from './OfferteEdit';
import type { OfferteFull, DocumentStatus, WorkflowStatus } from '../../types';

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

const statusSteps: DocumentStatus[] = ['concept', 'offerte_gereed', 'verzonden', 'geaccepteerd'];
const statusLabels: Record<DocumentStatus, string> = {
  concept: 'Concept',
  offerte_gereed: 'Offerte',
  verzonden: 'Aanvraag',
  geaccepteerd: 'Akkoord',
};

interface DetailDataField {
  label: string;
  value: string;
  icon?: React.ReactNode;
  span?: boolean;
}

function DetailField({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1 flex items-center gap-1.5">
        {icon}
        {label}
      </p>
      <p className="text-[13px] font-medium text-slate-800 dark:text-slate-200">{value}</p>
    </div>
  );
}

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-700/60">
      <h3 className="text-[13px] font-semibold text-slate-800 dark:text-slate-100">{title}</h3>
      {subtitle && <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">{subtitle}</p>}
    </div>
  );
}

interface HistoryEvent {
  label: string;
  time: string;
  isFirst?: boolean;
}

const mockHistory: HistoryEvent[] = [
  { label: 'Aangemaakt', time: 'Apr 14, 2026 09:49', isFirst: true },
];

const mockPhotos = [
  'https://images.pexels.com/photos/1396122/pexels-photo-1396122.jpeg?auto=compress&cs=tinysrgb&w=120&h=120&dpr=1',
];

interface OfferteDetailProps {
  offerte: OfferteFull;
  onBack: () => void;
}

export function OfferteDetail({ offerte, onBack }: OfferteDetailProps) {
  const [editing, setEditing] = useState(false);
  const [nextStep, setNextStep] = useState('Bel vrijdag om akkoord te vragen');
  const [plannedFor, setPlannedFor] = useState('');
  const [note, setNote] = useState('');
  const [savedNote, setSavedNote] = useState<string | null>(null);

  if (editing) {
    return <OfferteEdit offerte={offerte} onBack={() => setEditing(false)} />;
  }

  const wfCfg = workflowStatusConfig[offerte.workflowStatus];
  const docCfg = documentStatusConfig[offerte.documentStatus];
  const currentStepIdx = statusSteps.indexOf(offerte.documentStatus);
  const initials = offerte.client.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();

  const handleSave = () => {
    setSavedNote(note);
  };

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <button
            onClick={onBack}
            className="mt-0.5 flex items-center justify-center w-7 h-7 rounded-lg text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-all"
            aria-label="Terug"
          >
            <ArrowLeft size={15} />
          </button>
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100 tracking-tight">
                Offerte #{offerte.id}
              </h1>
              {offerte.documentStatus === 'offerte_gereed' && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-700 dark:bg-amber-400/15 dark:text-amber-400 ring-1 ring-inset ring-amber-200 dark:ring-amber-400/25 uppercase tracking-wide">
                  <AlertTriangle size={9} />
                  Controleer offerte
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5 mt-1 text-[12px] text-slate-500 dark:text-slate-400">
              <span className="font-medium text-slate-700 dark:text-slate-300">{offerte.client}</span>
              <ChevronRight size={12} className="text-slate-300 dark:text-slate-600" />
              <span>{offerte.workflow}</span>
              {offerte.amount != null && (
                <>
                  <ChevronRight size={12} className="text-slate-300 dark:text-slate-600" />
                  <span className="font-semibold text-slate-700 dark:text-slate-300">
                    € {offerte.amount.toLocaleString('nl-NL', { minimumFractionDigits: 2 })}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button variant="secondary" size="sm">
            <ExternalLink size={12} />
            Bekijk offerte
          </Button>
          <Button variant="secondary" size="sm">
            <Download size={12} />
            PDF downloaden
          </Button>
          <Button variant="primary" size="sm" onClick={() => setEditing(true)}>
            <Pencil size={12} />
            Offerte bewerken
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_300px] gap-5 items-start">
        <div className="space-y-4">
          <Card noPadding>
            <SectionHeader title="Project & klant" subtitle="Kerncijfers en gegevens uit de aanvraag" />

            <div className="p-5 grid grid-cols-2 sm:grid-cols-4 gap-4 border-b border-slate-100 dark:border-slate-700/60">
              {[
                { label: 'Totaal', value: offerte.amount != null ? `€ ${offerte.amount.toLocaleString('nl-NL', { minimumFractionDigits: 2 })}` : '—', icon: <Hash size={10} /> },
                { label: 'Oppervlakte', value: '22.0 m²', icon: <Layers size={10} /> },
                { label: 'Soort werk', value: 'interior', icon: <Wrench size={10} /> },
                { label: 'Controle', value: 'Even nalopen', icon: <AlertTriangle size={10} />, accent: true },
              ].map(({ label, value, icon, accent }) => (
                <div key={label} className={`rounded-lg p-3.5 ${accent ? 'bg-amber-50 dark:bg-amber-400/8 border border-amber-200 dark:border-amber-400/20' : 'bg-slate-50 dark:bg-slate-700/30 border border-slate-100 dark:border-slate-700/40'}`}>
                  <p className={`text-[10px] font-semibold uppercase tracking-wider mb-1 flex items-center gap-1 ${accent ? 'text-amber-600 dark:text-amber-400' : 'text-slate-400 dark:text-slate-500'}`}>
                    {icon}
                    {label}
                  </p>
                  <p className={`text-[14px] font-bold ${accent ? 'text-amber-700 dark:text-amber-300' : 'text-slate-800 dark:text-slate-100'}`}>{value}</p>
                </div>
              ))}
            </div>

            <div className="p-5 border-b border-slate-100 dark:border-slate-700/60">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-4">Contact</p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <DetailField label="Naam" value={offerte.client} icon={<User size={9} />} />
                <DetailField label="E-mail" value="demo@demo.nl" icon={<Mail size={9} />} />
                <DetailField label="Telefoon" value="1232456" icon={<Phone size={9} />} />
              </div>
            </div>

            <div className="p-5 border-b border-slate-100 dark:border-slate-700/60">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-4">Locatie & werk</p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <DetailField label="Adres" value="d, d, d, d, NL" icon={<MapPin size={9} />} />
                <DetailField label="Oppervlakte" value="22.0 m²" icon={<Layers size={9} />} />
                <DetailField label="Soort werk" value="interior" icon={<Wrench size={9} />} />
              </div>
            </div>

            <div className="p-5">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-3">Wat wil de klant?</p>
              <div className="rounded-lg bg-slate-50 dark:bg-slate-700/30 border border-slate-100 dark:border-slate-700/40 p-4 min-h-[80px]">
                <p className="text-[13px] text-slate-700 dark:text-slate-300 leading-relaxed">d</p>
              </div>
            </div>
          </Card>
        </div>

        <div className="space-y-4">
          <Card noPadding>
            <div className="px-4 py-3.5 border-b border-slate-100 dark:border-slate-700/60">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Huidige status</p>
            </div>
            <div className="p-4">
              <div className="flex items-center gap-1 mb-3">
                {statusSteps.map((step, idx) => {
                  const isActive = idx === currentStepIdx;
                  const isPast = idx < currentStepIdx;
                  const cfg = documentStatusConfig[step];
                  return (
                    <div key={step} className="flex items-center gap-1 flex-1 min-w-0">
                      <div className={`flex-1 flex flex-col items-center`}>
                        <span className={`inline-flex items-center justify-center px-2 py-1 rounded text-[10px] font-semibold ring-1 ring-inset w-full text-center truncate transition-all ${
                          isActive ? cfg.className : isPast ? 'bg-emerald-50 text-emerald-600 ring-emerald-200 dark:bg-emerald-400/10 dark:text-emerald-400 dark:ring-emerald-400/20' : 'bg-slate-50 text-slate-400 ring-slate-200 dark:bg-slate-700/20 dark:text-slate-500 dark:ring-slate-700/40'
                        }`}>
                          {isActive && statusLabels[step]}
                          {isPast && <CheckCircle2 size={10} className="inline mr-0.5" />}
                          {isPast && statusLabels[step]}
                          {!isActive && !isPast && statusLabels[step]}
                        </span>
                      </div>
                      {idx < statusSteps.length - 1 && (
                        <div className={`w-2 h-px shrink-0 ${isPast ? 'bg-emerald-300 dark:bg-emerald-400/30' : 'bg-slate-200 dark:bg-slate-700/60'}`} />
                      )}
                    </div>
                  );
                })}
              </div>
              <div className="flex flex-wrap gap-1.5 pt-2">
                <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium ring-1 ring-inset ${wfCfg.className}`}>
                  <span className="w-1.5 h-1.5 rounded-full bg-current opacity-60" />
                  {wfCfg.label}
                </span>
                <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium ring-1 ring-inset ${docCfg.className}`}>
                  <span className="w-1.5 h-1.5 rounded-full bg-current opacity-60" />
                  {docCfg.label}
                </span>
              </div>
            </div>
          </Card>

          <Card noPadding>
            <div className="px-4 py-3.5 border-b border-slate-100 dark:border-slate-700/60">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Nu doen</p>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-2.5">Opvolging plannen</p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mb-3">Alleen zichtbaar voor jouw team.</p>
                <div className="space-y-2.5">
                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 dark:text-slate-400 mb-1.5">Volgende stap</label>
                    <input
                      type="text"
                      value={nextStep}
                      onChange={e => setNextStep(e.target.value)}
                      placeholder="Bel vrijdag om akkoord te vragen"
                      className="w-full px-3 py-2 text-[12px] text-slate-800 dark:text-slate-200 bg-white dark:bg-slate-700/40 border border-slate-200 dark:border-slate-600 rounded-lg placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:focus:ring-brand-400 transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 dark:text-slate-400 mb-1.5">
                      <span className="flex items-center gap-1.5">
                        <Calendar size={10} />
                        Gepland voor
                      </span>
                    </label>
                    <input
                      type="datetime-local"
                      value={plannedFor}
                      onChange={e => setPlannedFor(e.target.value)}
                      className="w-full px-3 py-2 text-[12px] text-slate-800 dark:text-slate-200 bg-white dark:bg-slate-700/40 border border-slate-200 dark:border-slate-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 dark:focus:ring-brand-400 transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 dark:text-slate-400 mb-1.5">
                      <span className="flex items-center gap-1.5">
                        <StickyNote size={10} />
                        Interne notitie
                      </span>
                    </label>
                    <textarea
                      value={note}
                      onChange={e => setNote(e.target.value)}
                      placeholder="Korte notitie over prijs, planning of afspraak"
                      rows={3}
                      className="w-full px-3 py-2 text-[12px] text-slate-800 dark:text-slate-200 bg-white dark:bg-slate-700/40 border border-slate-200 dark:border-slate-600 rounded-lg placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:focus:ring-brand-400 transition-colors resize-none leading-relaxed"
                    />
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 pt-1">
                <Button variant="primary" size="sm" onClick={handleSave}>
                  Opslaan
                </Button>
                {savedNote && (
                  <span className="text-[11px] text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 size={11} />
                    Direct opgeslagen
                  </span>
                )}
              </div>
            </div>
          </Card>

          <Card noPadding>
            <div className="px-4 py-3.5 border-b border-slate-100 dark:border-slate-700/60 flex items-center justify-between">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Historie</p>
              <button className="text-[11px] font-medium text-brand-600 dark:text-brand-400 hover:text-brand-700 dark:hover:text-brand-300 transition-colors">
                Logboek
              </button>
            </div>
            <div className="p-4">
              <div className="space-y-3">
                {mockHistory.map((event, idx) => (
                  <div key={idx} className="flex items-start gap-3">
                    <div className="flex flex-col items-center gap-1 shrink-0 pt-0.5">
                      <div className="w-2 h-2 rounded-full bg-brand-500 dark:bg-brand-400 ring-2 ring-brand-100 dark:ring-brand-400/20" />
                      {idx < mockHistory.length - 1 && (
                        <div className="w-px flex-1 bg-slate-200 dark:bg-slate-700 min-h-[16px]" />
                      )}
                    </div>
                    <div>
                      <p className="text-[12px] font-semibold text-slate-700 dark:text-slate-200">{event.label}</p>
                      <div className="flex items-center gap-1 mt-0.5">
                        <Clock size={10} className="text-slate-400 dark:text-slate-500" />
                        <span className="text-[11px] text-brand-600 dark:text-brand-400">{event.time}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          <Card noPadding>
            <div className="px-4 py-3.5 border-b border-slate-100 dark:border-slate-700/60 flex items-center justify-between">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Foto's van de klant</p>
              <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">{mockPhotos.length}</span>
            </div>
            <div className="p-4">
              <div className="grid grid-cols-4 gap-2">
                {mockPhotos.map((src, idx) => (
                  <div key={idx} className="relative group aspect-square rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700/60 cursor-pointer">
                    <img src={src} alt={`Foto ${idx + 1}`} className="w-full h-full object-cover transition-transform group-hover:scale-105" />
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                      <ExternalLink size={12} className="text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </div>
                ))}
                <div className="aspect-square rounded-lg border-2 border-dashed border-slate-200 dark:border-slate-700/60 flex items-center justify-center cursor-pointer hover:border-brand-400 dark:hover:border-brand-500 hover:bg-brand-50/50 dark:hover:bg-brand-400/5 transition-all group">
                  <ImageIcon size={14} className="text-slate-300 dark:text-slate-600 group-hover:text-brand-400 transition-colors" />
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
