import { useState, useRef } from 'react';
import { Upload, X } from 'lucide-react';
import { workspaceName } from '../data/mockData';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';

const TOTAL_STEPS = 4;

const STEP_LABELS: Record<number, string> = {
  1: 'Jouw gegevens',
  2: 'Project details',
  3: "Foto's",
  4: 'Controleer',
};

const WERK_OPTIONS = ['Binnen', 'Buiten', 'Binnen & buiten', 'Overig / herstelwerk'];

interface FormData {
  naam: string;
  email: string;
  telefoon: string;
  werkType: string;
  oppervlakte: string;
  adres: string;
  woonplaats: string;
  postcode: string;
  provincie: string;
  omschrijving: string;
  fotos: File[];
}

function StepBar({ current }: { current: number }) {
  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
          Stap {current} van {TOTAL_STEPS}
        </span>
        <span className="text-xs font-semibold text-slate-900 dark:text-slate-100">
          {STEP_LABELS[current]}
        </span>
      </div>
      <div className="h-1 w-full bg-slate-100 dark:bg-slate-700/60 rounded-full overflow-hidden">
        <div
          className="h-full bg-brand-600 dark:bg-brand-500 rounded-full transition-all duration-500 ease-out"
          style={{ width: `${(current / TOTAL_STEPS) * 100}%` }}
        />
      </div>
    </div>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1.5">
      {children}
    </label>
  );
}

function TextInput({
  placeholder,
  value,
  onChange,
  type = 'text',
}: {
  placeholder?: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}) {
  return (
    <input
      type={type}
      placeholder={placeholder}
      value={value}
      onChange={e => onChange(e.target.value)}
      className="w-full h-9 px-3 rounded-lg border border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-800/80 text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 dark:focus:border-brand-500 transition-all duration-150"
    />
  );
}

function NavRow({
  onBack,
  onNext,
  nextLabel = 'Ga verder',
  showBack = true,
}: {
  onBack?: () => void;
  onNext: () => void;
  nextLabel?: string;
  showBack?: boolean;
}) {
  return (
    <div className="flex items-center justify-between pt-5 mt-5 border-t border-slate-100 dark:border-slate-700/60">
      <div>
        {showBack && (
          <Button variant="secondary" size="sm" onClick={onBack}>
            Vorige
          </Button>
        )}
      </div>
      <Button variant="primary" size="sm" onClick={onNext}>
        {nextLabel}
      </Button>
    </div>
  );
}

function Step1({
  data,
  onChange,
  onNext,
}: {
  data: FormData;
  onChange: (k: keyof FormData, v: string) => void;
  onNext: () => void;
}) {
  return (
    <div>
      <div className="mb-5">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Jouw gegevens</h2>
      </div>

      <div className="space-y-4">
        <div>
          <FieldLabel>Volledige naam *</FieldLabel>
          <TextInput placeholder="Jan Jansen" value={data.naam} onChange={v => onChange('naam', v)} />
        </div>
        <div>
          <FieldLabel>E-mailadres *</FieldLabel>
          <TextInput type="email" placeholder="jan@voorbeeld.nl" value={data.email} onChange={v => onChange('email', v)} />
        </div>
        <div>
          <FieldLabel>Telefoonnummer *</FieldLabel>
          <TextInput type="tel" placeholder="+31 6 12345678" value={data.telefoon} onChange={v => onChange('telefoon', v)} />
        </div>
      </div>

      <NavRow showBack={false} onNext={onNext} />
    </div>
  );
}

function Step2({
  data,
  onChange,
  onBack,
  onNext,
}: {
  data: FormData;
  onChange: (k: keyof FormData, v: string) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  return (
    <div>
      <div className="mb-5">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Project details</h2>
      </div>

      <div className="space-y-5">
        <div>
          <FieldLabel>Wat wil je laten schilderen? *</FieldLabel>
          <div className="grid grid-cols-2 gap-2 mt-1">
            {WERK_OPTIONS.map(opt => (
              <button
                key={opt}
                type="button"
                onClick={() => onChange('werkType', opt)}
                className={`h-9 px-3 rounded-lg border text-sm font-medium transition-all duration-150 ${
                  data.werkType === opt
                    ? 'bg-brand-600 text-white border-brand-600 dark:bg-brand-600 dark:border-brand-600'
                    : 'bg-white dark:bg-slate-800/80 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700/60 hover:border-brand-400 dark:hover:border-brand-500 hover:text-brand-600 dark:hover:text-brand-400'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>

        <div>
          <FieldLabel>Oppervlakte (m²) *</FieldLabel>
          <TextInput placeholder="35" value={data.oppervlakte} onChange={v => onChange('oppervlakte', v)} />
          <p className="mt-1.5 text-xs text-slate-400 dark:text-slate-500">
            Weet je het niet precies?{' '}
            <span className="text-brand-600 dark:text-brand-400 font-medium">Een schatting is prima.</span>
          </p>
        </div>

        <div>
          <FieldLabel>Adres *</FieldLabel>
          <div className="space-y-2">
            <TextInput placeholder="Straat en huisnummer" value={data.adres} onChange={v => onChange('adres', v)} />
            <div className="grid grid-cols-3 gap-2">
              <TextInput placeholder="Woonplaats" value={data.woonplaats} onChange={v => onChange('woonplaats', v)} />
              <TextInput placeholder="Postcode" value={data.postcode} onChange={v => onChange('postcode', v)} />
              <TextInput placeholder="Provincie" value={data.provincie} onChange={v => onChange('provincie', v)} />
            </div>
          </div>
        </div>

        <div>
          <FieldLabel>Omschrijving *</FieldLabel>
          <textarea
            placeholder="Bijv. woonkamer en hal, alleen wanden, kleine reparaties gewenst."
            value={data.omschrijving}
            onChange={e => onChange('omschrijving', e.target.value)}
            rows={4}
            className="w-full rounded-lg border border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-800/80 text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-600 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 dark:focus:border-brand-500 transition-all duration-150 resize-none"
          />
        </div>
      </div>

      <NavRow onBack={onBack} onNext={onNext} />
    </div>
  );
}

function Step3({
  data,
  onFilesChange,
  onBack,
  onNext,
}: {
  data: FormData;
  onFilesChange: (files: File[]) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    const arr = Array.from(incoming).slice(0, 5);
    onFilesChange(arr);
  };

  return (
    <div>
      <div className="mb-5">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Foto's van het werk</h2>
        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
          Hoe beter de foto's, hoe nauwkeuriger de prijs
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        className="hidden"
        onChange={e => handleFiles(e.target.files)}
      />

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={e => e.preventDefault()}
        onDrop={e => { e.preventDefault(); handleFiles(e.dataTransfer.files); }}
        className="w-full rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-700/60 bg-slate-50/80 dark:bg-slate-800/30 hover:bg-brand-50/60 dark:hover:bg-brand-400/5 hover:border-brand-300 dark:hover:border-brand-500/50 transition-all duration-200 py-12 px-4 flex flex-col items-center gap-3 group"
      >
        <div className="flex items-center justify-center w-10 h-10 rounded-lg border border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-800/80 group-hover:border-brand-300 dark:group-hover:border-brand-500/50 transition-colors">
          <Upload size={17} className="text-slate-400 dark:text-slate-500 group-hover:text-brand-500 dark:group-hover:text-brand-400 transition-colors" />
        </div>
        <div className="text-center">
          <p className="text-sm font-medium text-slate-700 dark:text-slate-300 group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors">
            Klik om foto's toe te voegen
          </p>
          <p className="text-xs text-brand-600 dark:text-brand-400 mt-0.5 font-medium">
            1–5 foto's · JPG, PNG of WebP · max 15 MB per foto
          </p>
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1.5">
            {data.fotos.length > 0
              ? `${data.fotos.length} bestand${data.fotos.length > 1 ? 'en' : ''} geselecteerd`
              : 'Nog geen bestanden geselecteerd'}
          </p>
        </div>
      </button>

      {data.fotos.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {data.fotos.map((f, i) => (
            <div
              key={i}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40 border border-slate-200 dark:border-slate-700/60"
            >
              <span className="text-xs text-slate-600 dark:text-slate-300 truncate max-w-[160px]">{f.name}</span>
              <button
                onClick={e => { e.stopPropagation(); onFilesChange(data.fotos.filter((_, j) => j !== i)); }}
                className="text-slate-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      <NavRow onBack={onBack} onNext={onNext} />
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-slate-100 dark:border-slate-700/60 last:border-0">
      <span className="text-xs text-slate-500 dark:text-slate-400">{label}</span>
      <span className="text-xs font-semibold text-slate-900 dark:text-slate-100">{value}</span>
    </div>
  );
}

function Step4({
  data,
  onBack,
  onSubmit,
}: {
  data: FormData;
  onBack: () => void;
  onSubmit: () => void;
}) {
  const locatie = [data.adres, data.woonplaats, data.postcode, data.provincie]
    .filter(Boolean)
    .join(', ') || '—';

  return (
    <div>
      <div className="mb-5">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Controleer en verstuur</h2>
      </div>

      <div className="rounded-xl border border-slate-200 dark:border-slate-700/60 overflow-hidden mb-4">
        <div className="px-4 py-2.5 bg-slate-50 dark:bg-slate-800/40 border-b border-slate-100 dark:border-slate-700/60">
          <span className="text-[10px] font-semibold tracking-widest uppercase text-slate-400 dark:text-slate-500">
            Jouw gegevens
          </span>
        </div>
        <div className="px-4">
          <SummaryRow label="Naam" value={data.naam || '—'} />
          <SummaryRow label="E-mail" value={data.email || '—'} />
          <SummaryRow label="Telefoon" value={data.telefoon || '—'} />
          <SummaryRow label="Werkzaamheden" value={data.werkType || '—'} />
          <SummaryRow label="Oppervlakte" value={data.oppervlakte ? `${data.oppervlakte} m2` : '—'} />
          <SummaryRow label="Locatie" value={locatie} />
          <SummaryRow label="Foto's" value={String(data.fotos.length)} />
        </div>
      </div>

      <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
        Gratis en vrijblijvend. Binnen een paar minuten geregeld.
      </p>

      <NavRow onBack={onBack} onNext={onSubmit} nextLabel="Offerte aanvragen" />
    </div>
  );
}

function LoadingOverlay() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30 dark:bg-[#080f1a]/60 backdrop-blur-sm">
      <div className="bg-white dark:bg-slate-800/95 rounded-2xl border border-slate-200 dark:border-slate-700/60 shadow-card-md px-10 py-10 flex flex-col items-center gap-4 min-w-[300px]">
        <div className="w-8 h-8 rounded-full border-2 border-slate-200 dark:border-slate-700 border-t-brand-600 dark:border-t-brand-400 animate-spin" />
        <div className="text-center">
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">We verwerken je aanvraag</p>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Dit duurt meestal een paar seconden.</p>
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-2">Foto's analyseren...</p>
        </div>
      </div>
    </div>
  );
}

export function Intake({ onNavigate }: { onNavigate?: (id: string) => void }) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<FormData>({
    naam: '',
    email: '',
    telefoon: '',
    werkType: '',
    oppervlakte: '',
    adres: '',
    woonplaats: '',
    postcode: '',
    provincie: '',
    omschrijving: '',
    fotos: [],
  });

  const setField = (k: keyof FormData, v: string) => setData(prev => ({ ...prev, [k]: v }));
  const setFiles = (fotos: File[]) => setData(prev => ({ ...prev, fotos }));

  const handleSubmit = () => {
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      onNavigate?.('offertes');
    }, 3000);
  };

  return (
    <div className="max-w-lg">
      {loading && <LoadingOverlay />}

      <div className="mb-5 flex items-center gap-2.5">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-brand-50 dark:bg-brand-400/10 border border-brand-100 dark:border-brand-400/20 shrink-0">
          <span className="text-brand-600 dark:text-brand-400 text-xs font-bold leading-none">S</span>
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-100 leading-tight">{workspaceName}</p>
          <p className="text-xs text-brand-600 dark:text-brand-400 font-medium leading-tight">Gratis en vrijblijvend</p>
        </div>
      </div>

      <StepBar current={step} />

      <Card>
        {step === 1 && <Step1 data={data} onChange={setField} onNext={() => setStep(2)} />}
        {step === 2 && <Step2 data={data} onChange={setField} onBack={() => setStep(1)} onNext={() => setStep(3)} />}
        {step === 3 && <Step3 data={data} onFilesChange={setFiles} onBack={() => setStep(2)} onNext={() => setStep(4)} />}
        {step === 4 && <Step4 data={data} onBack={() => setStep(3)} onSubmit={handleSubmit} />}
      </Card>
    </div>
  );
}
