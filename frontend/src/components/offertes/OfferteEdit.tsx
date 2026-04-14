import { useState } from 'react';
import { ArrowLeft, Plus, Trash2, FileText, ChevronDown } from 'lucide-react';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import type { OfferteFull } from '../../types';

interface RegelRow {
  id: string;
  omschrijving: string;
  toelichting: string;
  aantal: string;
  eenheid: string;
  prijs: string;
  soortWerk: string;
}

interface OfferteEditProps {
  offerte: OfferteFull;
  onBack: () => void;
}

const inputClass =
  'w-full px-3 py-2 text-[13px] text-slate-800 dark:text-slate-200 bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-lg placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:focus:ring-brand-400 focus:border-transparent transition-all';

const labelClass = 'block text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1.5';

function FormLabel({ children }: { children: React.ReactNode }) {
  return <label className={labelClass}>{children}</label>;
}

function FormInput({
  value,
  onChange,
  placeholder,
  type = 'text',
  readOnly,
}: {
  value: string;
  onChange?: (v: string) => void;
  placeholder?: string;
  type?: string;
  readOnly?: boolean;
}) {
  return (
    <input
      type={type}
      value={value}
      onChange={e => onChange?.(e.target.value)}
      placeholder={placeholder}
      readOnly={readOnly}
      className={`${inputClass} ${readOnly ? 'bg-slate-50 dark:bg-slate-800/30 text-slate-500 dark:text-slate-400 cursor-default' : ''}`}
    />
  );
}

function SectionCard({
  title,
  subtitle,
  children,
  action,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <Card noPadding>
      <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-700/60 flex items-center justify-between gap-4">
        <div>
          <h3 className="text-[13px] font-semibold text-slate-800 dark:text-slate-100">{title}</h3>
          {subtitle && <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">{subtitle}</p>}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      <div className="p-5">{children}</div>
    </Card>
  );
}

function SelectInput({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className={`${inputClass} appearance-none pr-8`}
      >
        {options.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <ChevronDown size={13} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
    </div>
  );
}

function RegelRow({
  regel,
  onChange,
  onRemove,
  index,
}: {
  regel: RegelRow;
  onChange: (id: string, field: keyof RegelRow, value: string) => void;
  onRemove: (id: string) => void;
  index: number;
}) {
  const total =
    parseFloat(regel.aantal || '0') * parseFloat(regel.prijs || '0');

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700/60 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-50 dark:bg-slate-800/40 border-b border-slate-200 dark:border-slate-700/60">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
          Regel {index + 1}
        </span>
        <div className="flex items-center gap-3">
          <span className="text-[13px] font-bold text-slate-800 dark:text-slate-100">
            {isNaN(total) ? '—' : `€ ${total.toLocaleString('nl-NL', { minimumFractionDigits: 2 })}`}
          </span>
          <button
            type="button"
            onClick={() => onRemove(regel.id)}
            className="flex items-center justify-center w-6 h-6 rounded-md text-slate-400 dark:text-slate-500 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-400/10 transition-all"
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>
      <div className="p-4 grid grid-cols-1 gap-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <FormLabel>Omschrijving</FormLabel>
            <FormInput
              value={regel.omschrijving}
              onChange={v => onChange(regel.id, 'omschrijving', v)}
              placeholder="Bijv. Buitenschilderwerk woonhuis"
            />
          </div>
          <div>
            <FormLabel>Toelichting</FormLabel>
            <FormInput
              value={regel.toelichting}
              onChange={v => onChange(regel.id, 'toelichting', v)}
              placeholder="Toelichting"
            />
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div>
            <FormLabel>Aantal</FormLabel>
            <FormInput
              value={regel.aantal}
              onChange={v => onChange(regel.id, 'aantal', v)}
              placeholder="0"
              type="number"
            />
          </div>
          <div>
            <FormLabel>Eenheid</FormLabel>
            <FormInput
              value={regel.eenheid}
              onChange={v => onChange(regel.id, 'eenheid', v)}
              placeholder="m²"
            />
          </div>
          <div>
            <FormLabel>Prijs</FormLabel>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[13px] text-slate-400 dark:text-slate-500 pointer-events-none">€</span>
              <input
                type="number"
                value={regel.prijs}
                onChange={e => onChange(regel.id, 'prijs', e.target.value)}
                placeholder="0,00"
                className={`${inputClass} pl-7`}
              />
            </div>
          </div>
          <div>
            <FormLabel>Soort werk</FormLabel>
            <SelectInput
              value={regel.soortWerk}
              onChange={v => onChange(regel.id, 'soortWerk', v)}
              options={[
                { value: 'Arbeid', label: 'Arbeid' },
                { value: 'Materiaal', label: 'Materiaal' },
                { value: 'Overig', label: 'Overig' },
              ]}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export function OfferteEdit({ offerte, onBack }: OfferteEditProps) {
  const [klantNaam, setKlantNaam] = useState(offerte.client);
  const [klantEmail, setKlantEmail] = useState('demo@demo.nl');
  const [klantTelefoon, setKlantTelefoon] = useState('123456');
  const [klantLocatie, setKlantLocatie] = useState('');

  const [bedrijfNaam, setBedrijfNaam] = useState('Snoopy schilderwerken');
  const [bedrijfEmail, setBedrijfEmail] = useState('dvanlashout00@gmail.com');
  const [bedrijfTelefoon, setBedrijfTelefoon] = useState('12434545');

  const [referentie] = useState(`lead_${offerte.id}`);
  const [offerteDatum, setOfferteDatum] = useState('2026-04-14');
  const [geldigTot, setGeldigTot] = useState('2026-05-14');
  const [titel, setTitel] = useState('Offerte schilderwerk');
  const [subtitel, setSubtitel] = useState('');

  const [regels, setRegels] = useState<RegelRow[]>([
    {
      id: 'r1',
      omschrijving: 'Wanden schilderen',
      toelichting: '',
      aantal: '22',
      eenheid: 'm²',
      prijs: '25',
      soortWerk: 'Arbeid',
    },
  ]);

  const [korting, setKorting] = useState('5');
  const [vasteKosten, setVasteKosten] = useState('2450.00');
  const [btw, setBtw] = useState('21.0');

  const [inclusiefWerkzaamheden, setInclusiefWerkzaamheden] = useState('');
  const [nietInbegrepen, setNietInbegrepen] = useState('');
  const [opmerkingKlant, setOpmerkingKlant] = useState('');

  const subtotaalRegels = regels.reduce(
    (acc, r) => acc + parseFloat(r.aantal || '0') * parseFloat(r.prijs || '0'),
    0,
  );
  const kortingBedrag = subtotaalRegels * (parseFloat(korting || '0') / 100);
  const subtotaalNaKorting = subtotaalRegels - kortingBedrag + parseFloat(vasteKosten || '0');
  const btwBedrag = subtotaalNaKorting * (parseFloat(btw || '0') / 100);
  const totaal = subtotaalNaKorting + btwBedrag;

  const handleRegelChange = (id: string, field: keyof RegelRow, value: string) => {
    setRegels(prev => prev.map(r => (r.id === id ? { ...r, [field]: value } : r)));
  };

  const handleRegelRemove = (id: string) => {
    setRegels(prev => prev.filter(r => r.id !== id));
  };

  const handleAddRegel = () => {
    setRegels(prev => [
      ...prev,
      {
        id: `r${Date.now()}`,
        omschrijving: '',
        toelichting: '',
        aantal: '',
        eenheid: 'm²',
        prijs: '',
        soortWerk: 'Arbeid',
      },
    ]);
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
            <div className="flex items-center gap-2">
              <span className="text-[12px] text-slate-400 dark:text-slate-500">Offertes</span>
              <span className="text-[12px] text-slate-300 dark:text-slate-600">/</span>
              <span className="text-[12px] text-slate-500 dark:text-slate-400">#{offerte.id}</span>
              <span className="text-[12px] text-slate-300 dark:text-slate-600">/</span>
              <span className="text-[12px] font-medium text-slate-700 dark:text-slate-300">Bewerken</span>
            </div>
            <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100 tracking-tight mt-0.5">
              Offerte bewerken
            </h1>
            <p className="text-[12px] text-slate-500 dark:text-slate-400 mt-0.5">
              Pas hier de volledige offerte aan, sla de klant die dat.
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <SectionCard title="Klantgegevens" subtitle="Naam, contactinfo en locatie van de klant">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <FormLabel>Naam</FormLabel>
              <FormInput value={klantNaam} onChange={setKlantNaam} placeholder="Naam klant" />
            </div>
            <div>
              <FormLabel>E-mailadres</FormLabel>
              <FormInput value={klantEmail} onChange={setKlantEmail} placeholder="email@voorbeeld.nl" type="email" />
            </div>
            <div>
              <FormLabel>Telefoonnummer</FormLabel>
              <FormInput value={klantTelefoon} onChange={setKlantTelefoon} placeholder="06 12 34 56 78" />
            </div>
            <div>
              <FormLabel>Locatie / adres</FormLabel>
              <FormInput value={klantLocatie} onChange={setKlantLocatie} placeholder="Straat, stad" />
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Bedrijf" subtitle="Gegevens van jouw bedrijf op de offerte">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <FormLabel>Bedrijfsnaam</FormLabel>
              <FormInput value={bedrijfNaam} onChange={setBedrijfNaam} placeholder="Jouw bedrijfsnaam" />
            </div>
            <div>
              <FormLabel>E-mailadres</FormLabel>
              <FormInput value={bedrijfEmail} onChange={setBedrijfEmail} placeholder="email@bedrijf.nl" type="email" />
            </div>
            <div>
              <FormLabel>Telefoonnummer</FormLabel>
              <FormInput value={bedrijfTelefoon} onChange={setBedrijfTelefoon} placeholder="06 12 34 56 78" />
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Offerte" subtitle="Referentie, datums en omschrijving">
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <FormLabel>Referentienummer</FormLabel>
                <FormInput value={referentie} readOnly />
              </div>
              <div>
                <FormLabel>Offertedatum</FormLabel>
                <FormInput value={offerteDatum} onChange={setOfferteDatum} type="date" />
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <FormLabel>Geldig tot</FormLabel>
                <FormInput value={geldigTot} onChange={setGeldigTot} type="date" />
              </div>
              <div>
                <FormLabel>Titel</FormLabel>
                <FormInput value={titel} onChange={setTitel} placeholder="Bijv. Offerte schilderwerk" />
              </div>
            </div>
            <div>
              <FormLabel>Subtitel / korte omschrijving</FormLabel>
              <textarea
                value={subtitel}
                onChange={e => setSubtitel(e.target.value)}
                placeholder="Bijv. Binnenschilderwerk woonkamer, hal en trapopgang"
                rows={3}
                className={`${inputClass} resize-none leading-relaxed`}
              />
            </div>
          </div>
        </SectionCard>

        <SectionCard
          title="Regels / specificatie"
          subtitle="Voeg werkzaamheden, materialen of posten toe"
          action={
            <Button variant="secondary" size="sm" onClick={handleAddRegel}>
              <Plus size={12} />
              Regel toevoegen
            </Button>
          }
        >
          <div className="space-y-3">
            {regels.length === 0 && (
              <div className="rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-700/60 py-10 flex flex-col items-center gap-2 text-center">
                <FileText size={18} className="text-slate-300 dark:text-slate-600" />
                <p className="text-[12px] font-medium text-slate-400 dark:text-slate-500">Geen regels toegevoegd</p>
                <p className="text-[11px] text-slate-400 dark:text-slate-600">Klik op "Regel toevoegen" om te beginnen</p>
              </div>
            )}
            {regels.map((regel, index) => (
              <RegelRow
                key={regel.id}
                regel={regel}
                onChange={handleRegelChange}
                onRemove={handleRegelRemove}
                index={index}
              />
            ))}
          </div>
        </SectionCard>

        <SectionCard title="Prijs & aanpassingen" subtitle="Korting, vaste kosten en btw">
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <FormLabel>Korting (%)</FormLabel>
                <div className="relative">
                  <FormInput value={korting} onChange={setKorting} placeholder="0" type="number" />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[12px] text-slate-400 dark:text-slate-500 pointer-events-none">%</span>
                </div>
              </div>
              <div>
                <FormLabel>Vaste kosten (€)</FormLabel>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[13px] text-slate-400 dark:text-slate-500 pointer-events-none">€</span>
                  <input
                    type="number"
                    value={vasteKosten}
                    onChange={e => setVasteKosten(e.target.value)}
                    placeholder="0,00"
                    className={`${inputClass} pl-7`}
                  />
                </div>
              </div>
            </div>

            <div className="rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700/60">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Berekening</span>
              </div>
              <div className="divide-y divide-slate-100 dark:divide-slate-700/40">
                {[
                  { label: 'Subtotaal regels', value: subtotaalRegels },
                  { label: `Korting (${korting || 0}%)`, value: -kortingBedrag, muted: true },
                  { label: 'Vaste kosten', value: parseFloat(vasteKosten || '0') },
                  { label: 'Subtotaal excl. btw', value: subtotaalNaKorting },
                ].map(row => (
                  <div key={row.label} className="flex items-center justify-between px-4 py-2.5">
                    <span className={`text-[12px] ${row.muted ? 'text-slate-400 dark:text-slate-500' : 'text-slate-600 dark:text-slate-400'}`}>{row.label}</span>
                    <span className={`text-[13px] font-medium ${row.muted ? 'text-slate-400 dark:text-slate-500' : 'text-slate-800 dark:text-slate-200'}`}>
                      {row.value < 0 ? '−' : ''} € {Math.abs(row.value).toLocaleString('nl-NL', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                ))}
              </div>
              <div className="px-4 py-3 border-t border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-800/60">
                <div className="flex items-center gap-3">
                  <span className="text-[12px] text-slate-600 dark:text-slate-400 shrink-0">Btw (%)</span>
                  <input
                    type="number"
                    value={btw}
                    onChange={e => setBtw(e.target.value)}
                    placeholder="21"
                    className="w-24 px-3 py-1.5 text-[13px] text-slate-800 dark:text-slate-200 bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 transition-all"
                  />
                  <span className="text-[13px] font-medium text-slate-600 dark:text-slate-400 ml-auto">
                    € {btwBedrag.toLocaleString('nl-NL', { minimumFractionDigits: 2 })}
                  </span>
                </div>
              </div>
              <div className="flex items-center justify-between px-4 py-3.5 bg-brand-50 dark:bg-brand-400/8 border-t border-brand-100 dark:border-brand-400/20">
                <span className="text-[13px] font-bold text-brand-800 dark:text-brand-300">Totaal incl. btw</span>
                <span className="text-[16px] font-bold text-brand-700 dark:text-brand-300">
                  € {totaal.toLocaleString('nl-NL', { minimumFractionDigits: 2 })}
                </span>
              </div>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Tekstblokken / notities" subtitle="Tekst die op de offerte verschijnt">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <FormLabel>Inbegrepen werkzaamheden</FormLabel>
              <textarea
                value={inclusiefWerkzaamheden}
                onChange={e => setInclusiefWerkzaamheden(e.target.value)}
                rows={5}
                className={`${inputClass} resize-none leading-relaxed`}
              />
            </div>
            <div>
              <FormLabel>Niet inbegrepen / opmerkingen</FormLabel>
              <textarea
                value={nietInbegrepen}
                onChange={e => setNietInbegrepen(e.target.value)}
                rows={5}
                className={`${inputClass} resize-none leading-relaxed`}
              />
            </div>
            <div>
              <FormLabel>Opmerking voor klant</FormLabel>
              <textarea
                value={opmerkingKlant}
                onChange={e => setOpmerkingKlant(e.target.value)}
                rows={5}
                className={`${inputClass} resize-none leading-relaxed`}
              />
            </div>
          </div>
        </SectionCard>

        <div className="flex items-center gap-3 pt-1 pb-2">
          <Button variant="primary" size="md">
            Wijzigingen opslaan
          </Button>
          <Button variant="secondary" size="md" onClick={onBack}>
            Annuleren
          </Button>
          <div className="w-px h-5 bg-slate-200 dark:bg-slate-700 mx-1" />
          <Button variant="secondary" size="md">
            Offerte bekijken
          </Button>
          <Button variant="secondary" size="md">
            PDF opslaan
          </Button>
        </div>
      </div>
    </div>
  );
}
