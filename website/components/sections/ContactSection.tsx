"use client";

import { useState, FormEvent } from "react";
import { ArrowRight, CheckCircle2, Building2, Mail, Phone, User, MessageSquare } from "lucide-react";

interface FormData {
  naam: string;
  bedrijf: string;
  email: string;
  telefoon: string;
  bericht: string;
}

interface FormErrors {
  naam?: string;
  bedrijf?: string;
  email?: string;
  bericht?: string;
}

const INITIAL: FormData = {
  naam:     "",
  bedrijf:  "",
  email:    "",
  telefoon: "",
  bericht:  "",
};

export default function ContactSection() {
  const [form, setForm]       = useState<FormData>(INITIAL);
  const [errors, setErrors]   = useState<FormErrors>({});
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  function validate(): FormErrors {
    const e: FormErrors = {};
    if (!form.naam.trim())    e.naam    = "Vul je naam in.";
    if (!form.bedrijf.trim()) e.bedrijf = "Vul je bedrijfsnaam in.";
    if (!form.email.trim())   e.email   = "Vul je e-mailadres in.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email))
                              e.email   = "Voer een geldig e-mailadres in.";
    if (!form.bericht.trim()) e.bericht = "Vertel ons wat je wilt automatiseren.";
    return e;
  }

  function handleChange(
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    if (errors[name as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [name]: undefined }));
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }
    setLoading(true);
    // Simulate async submit
    await new Promise((r) => setTimeout(r, 800));
    setLoading(false);
    setSubmitted(true);
  }

  return (
    <section id="contact" className="py-14 lg:py-24 bg-white">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid lg:grid-cols-[1fr_1.35fr] gap-16 items-start">

          {/* ── Left: intro ──────────────────────────────── */}
          <div className="lg:sticky lg:top-32">
            <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-4">
              Contact
            </p>
            <h2 className="text-4xl lg:text-5xl font-semibold tracking-tight text-neutral-900 leading-tight text-balance mb-6">
              Plan een{" "}
              <span style={{ color: "#2563EB" }}>demo.</span>
            </h2>
            <p className="text-lg text-neutral-500 leading-relaxed mb-10">
              Laat je gegevens achter en we kijken samen welke processen
              binnen jouw bedrijf geautomatiseerd kunnen worden.
            </p>

            {/* Trust items */}
            <div className="flex flex-col gap-4">
              {[
                {
                  title: "Geen verplichtingen",
                  desc:  "Het gesprek is vrijblijvend. Geen pitch, geen verkoopdruk.",
                },
                {
                  title: "Concrete inzichten",
                  desc:  "Je gaat naar huis met een concreet beeld van je automatiseringspotentieel.",
                },
                {
                  title: "Snelle opvolging",
                  desc:  "We nemen binnen één werkdag contact met je op.",
                },
              ].map((item) => (
                <div key={item.title} className="flex items-start gap-3">
                  <div
                    className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                    style={{ backgroundColor: "rgba(37,99,235,0.1)" }}
                  >
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                      <path
                        d="M2.5 5l2 2L7.5 3"
                        stroke="#2563EB"
                        strokeWidth="1.4"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-neutral-800 mb-0.5">
                      {item.title}
                    </p>
                    <p className="text-sm text-neutral-500 leading-relaxed">
                      {item.desc}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* ── Right: form card ─────────────────────────── */}
          <div
            className="rounded-2xl p-8 bg-white"
            style={{
              border: "1px solid rgba(0,0,0,0.08)",
              boxShadow:
                "0 4px 6px -1px rgba(0,0,0,0.04), 0 16px 40px -8px rgba(0,0,0,0.08)",
            }}
          >
            {submitted ? (
              <SuccessState onReset={() => { setForm(INITIAL); setSubmitted(false); }} />
            ) : (
              <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">

                {/* Row: Naam + Bedrijf */}
                <div className="grid sm:grid-cols-2 gap-5">
                  <FormField
                    label="Naam"
                    icon={<User size={15} className="text-neutral-400" />}
                    error={errors.naam}
                  >
                    <input
                      name="naam"
                      type="text"
                      placeholder="Jan de Vries"
                      value={form.naam}
                      onChange={handleChange}
                      className={inputClass(!!errors.naam)}
                      autoComplete="name"
                    />
                  </FormField>

                  <FormField
                    label="Bedrijfsnaam"
                    icon={<Building2 size={15} className="text-neutral-400" />}
                    error={errors.bedrijf}
                  >
                    <input
                      name="bedrijf"
                      type="text"
                      placeholder="Bedrijf BV"
                      value={form.bedrijf}
                      onChange={handleChange}
                      className={inputClass(!!errors.bedrijf)}
                      autoComplete="organization"
                    />
                  </FormField>
                </div>

                {/* Row: Email + Telefoon */}
                <div className="grid sm:grid-cols-2 gap-5">
                  <FormField
                    label="E-mailadres"
                    icon={<Mail size={15} className="text-neutral-400" />}
                    error={errors.email}
                  >
                    <input
                      name="email"
                      type="email"
                      placeholder="jan@bedrijf.nl"
                      value={form.email}
                      onChange={handleChange}
                      className={inputClass(!!errors.email)}
                      autoComplete="email"
                    />
                  </FormField>

                  <FormField
                    label="Telefoonnummer"
                    icon={<Phone size={15} className="text-neutral-400" />}
                    optional
                  >
                    <input
                      name="telefoon"
                      type="tel"
                      placeholder="+31 6 12345678"
                      value={form.telefoon}
                      onChange={handleChange}
                      className={inputClass(false)}
                      autoComplete="tel"
                    />
                  </FormField>
                </div>

                {/* Textarea */}
                <FormField
                  label="Wat wil je automatiseren?"
                  icon={<MessageSquare size={15} className="text-neutral-400" />}
                  error={errors.bericht}
                >
                  <textarea
                    name="bericht"
                    rows={4}
                    placeholder="Beschrijf kort welke processen tijd kosten of foutgevoelig zijn. Denk aan: documentverwerking, e-mailafhandeling, rapportages, CRM-updates…"
                    value={form.bericht}
                    onChange={handleChange}
                    className={`${inputClass(!!errors.bericht)} resize-none`}
                  />
                </FormField>

                {/* Submit */}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-2 py-3.5 rounded-full text-[0.9375rem] font-semibold text-white transition-all duration-150 hover:opacity-90 active:scale-[0.99] disabled:opacity-60 disabled:cursor-not-allowed"
                  style={{ backgroundColor: "#2563EB" }}
                >
                  {loading ? (
                    <>
                      <Spinner />
                      Versturen…
                    </>
                  ) : (
                    <>
                      Offerte aanvragen
                      <ArrowRight size={16} />
                    </>
                  )}
                </button>

                <p className="text-xs text-neutral-400 text-center">
                  Geen spam. We gebruiken je gegevens alleen om contact met je op te nemen.
                </p>
              </form>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ─── Sub-components ─────────────────────────────────────── */

function FormField({
  label,
  icon,
  error,
  optional,
  children,
}: {
  label: string;
  icon?: React.ReactNode;
  error?: string;
  optional?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-neutral-700 flex items-center gap-1.5">
          {icon}
          {label}
        </label>
        {optional && (
          <span className="text-xs text-neutral-400">Optioneel</span>
        )}
      </div>
      {children}
      {error && (
        <p className="text-xs font-medium" style={{ color: "#dc2626" }}>
          {error}
        </p>
      )}
    </div>
  );
}

function SuccessState({ onReset }: { onReset: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 gap-5">
      <div
        className="w-16 h-16 rounded-full flex items-center justify-center"
        style={{ backgroundColor: "rgba(37,99,235,0.08)" }}
      >
        <CheckCircle2 size={32} style={{ color: "#2563EB" }} />
      </div>
      <div>
        <h3 className="text-xl font-semibold text-neutral-900 mb-2">
          Bedankt, we nemen snel contact met je op.
        </h3>
        <p className="text-neutral-500 text-sm leading-relaxed max-w-xs mx-auto">
          We hebben je aanvraag ontvangen en komen binnen één werkdag bij je terug.
        </p>
      </div>
      <button
        onClick={onReset}
        className="text-sm font-medium transition-colors"
        style={{ color: "#2563EB" }}
      >
        Nog een aanvraag indienen
      </button>
    </div>
  );
}

function Spinner() {
  return (
    <svg
      className="animate-spin"
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
    >
      <circle
        cx="8"
        cy="8"
        r="6"
        stroke="rgba(255,255,255,0.3)"
        strokeWidth="2"
      />
      <path
        d="M8 2a6 6 0 0 1 6 6"
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function inputClass(hasError: boolean) {
  return [
    "w-full px-4 py-2.5 rounded-xl text-sm text-neutral-800 bg-neutral-50 outline-none",
    "transition-all duration-150 placeholder:text-neutral-300",
    "focus:bg-white",
    hasError
      ? "border border-red-300 focus:border-red-400 focus:ring-2 focus:ring-red-100"
      : "border border-neutral-200 focus:border-blue-400 focus:ring-2 focus:ring-blue-50",
  ].join(" ");
}
