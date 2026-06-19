"use client";

import { useState, useEffect, FormEvent } from "react";
import {
  ArrowRight, CheckCircle2, Building2, Mail,
  Phone, User, MessageSquare, AlertCircle,
} from "lucide-react";

interface FormData {
  naam: string; bedrijf: string; email: string;
  telefoon: string; bericht: string;
}
interface FormErrors {
  naam?: string; bedrijf?: string; email?: string; bericht?: string;
}

const INITIAL: FormData = { naam: "", bedrijf: "", email: "", telefoon: "", bericht: "" };

const BENEFITS = [
  "No commitment required",
  "Concrete proposal with expected ROI",
  "Response within 1 business day",
  "Live demo of Inversiq on your processes",
];

function useReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const h = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, []);
  return reduced;
}

export default function DemoForm() {
  const [form, setForm]               = useState<FormData>(INITIAL);
  const [errors, setErrors]           = useState<FormErrors>({});
  const [submitted, setSubmitted]     = useState(false);
  const [loading, setLoading]         = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitHover, setSubmitHover] = useState(false);
  const reducedMotion                 = useReducedMotion();

  const [pageReady, setPageReady] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setPageReady(true), 80);
    return () => clearTimeout(t);
  }, []);

  const [benefitsReady, setBenefitsReady] = useState(false);
  useEffect(() => {
    if (!pageReady || reducedMotion) { setBenefitsReady(true); return; }
    const t = setTimeout(() => setBenefitsReady(true), 400);
    return () => clearTimeout(t);
  }, [pageReady, reducedMotion]);

  function validate(): FormErrors {
    const e: FormErrors = {};
    if (!form.naam.trim())    e.naam    = "Please enter your name.";
    if (!form.bedrijf.trim()) e.bedrijf = "Please enter your company name.";
    if (!form.email.trim())   e.email   = "Please enter your email address.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email))
                              e.email   = "Please enter a valid email address.";
    if (!form.bericht.trim()) e.bericht = "Please tell us what you want to automate.";
    return e;
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    if (errors[name as keyof FormErrors])
      setErrors((prev) => ({ ...prev, [name]: undefined }));
    if (serverError) setServerError(null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }
    setLoading(true);
    setServerError(null);
    try {
      const res  = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) { setServerError(data.error ?? "Something went wrong. Please try again."); return; }
      setSubmitted(true);
    } catch {
      setServerError("Could not connect. Please check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }

  function revealStyle(delay = 0) {
    if (reducedMotion) return {};
    return {
      opacity:    pageReady ? 1 : 0,
      transform:  pageReady ? "translateY(0px)" : "translateY(20px)",
      transition: `opacity 600ms ease ${delay}ms, transform 600ms ease ${delay}ms`,
    };
  }

  return (
    <div className="min-h-screen bg-white">
      <style>{`
        @keyframes imageFloat { 0%,100% { transform: translateY(0px); } 50% { transform: translateY(-6px); } }
      `}</style>

      <div className="max-w-6xl mx-auto px-6 pt-32 pb-20">
        <div className="grid lg:grid-cols-[1fr_1.75fr] gap-10 xl:gap-14 items-start">

          {/* Left */}
          <div className="flex flex-col gap-6 lg:sticky lg:top-32" style={revealStyle(0)}>
            <div style={{ animation: reducedMotion ? "none" : "imageFloat 8s ease-in-out infinite" }}>
              <div className="w-full overflow-hidden rounded-2xl"
                style={{ aspectRatio: "4 / 5", border: "1px solid rgba(0,0,0,0.07)", boxShadow: "0 4px 24px -4px rgba(0,0,0,0.1)" }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="https://images.unsplash.com/photo-1551434678-e076c223a692?w=800&q=80&auto=format&fit=crop&crop=top"
                  alt="Inversiq platform session"
                  className="w-full h-full object-cover"
                  style={{ objectPosition: "center 15%", filter: "saturate(0.8) brightness(0.93)" }}
                  loading="eager"
                />
              </div>
            </div>

            <div className="rounded-2xl p-6"
              style={{ backgroundColor: "#f8fafc", border: "1px solid rgba(0,0,0,0.07)" }}>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-5 h-0.5 rounded-full" style={{ backgroundColor: "#2563EB" }} />
                <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "#2563EB" }}>
                  What to expect
                </span>
              </div>
              <ul className="flex flex-col gap-3">
                {BENEFITS.map((b, i) => (
                  <li key={b} className="flex items-center gap-2.5"
                    style={reducedMotion ? {} : {
                      opacity:    benefitsReady ? 1 : 0,
                      transform:  benefitsReady ? "translateY(0px)" : "translateY(8px)",
                      transition: `opacity 400ms ease ${i * 80}ms, transform 400ms ease ${i * 80}ms`,
                    }}>
                    <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: "rgba(37,99,235,0.09)" }}>
                      <svg width="9" height="9" viewBox="0 0 9 9" fill="none">
                        <path d="M1.5 4.5l2 2 4-4" stroke="#2563EB" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </div>
                    <span className="text-sm text-neutral-600">{b}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Right: form */}
          <div style={revealStyle(100)}>
            <div className="mb-8">
              <p className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: "#2563EB" }}>
                Free · No commitment
              </p>
              <h1 className="text-3xl lg:text-4xl font-bold tracking-tight text-neutral-900 mb-3">
                Request a Demo.
              </h1>
              <p className="text-base text-neutral-500 leading-relaxed max-w-md">
                Tell us which processes cost your team time. We&apos;ll show you how Inversiq
                automates them — and what that concretely delivers.
              </p>
            </div>

            {submitted ? (
              <SuccessState />
            ) : (
              <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">

                <div className="grid sm:grid-cols-2 gap-4">
                  <Field label="Name" icon={<User size={14} className="text-neutral-400" />} error={errors.naam}>
                    <input name="naam" type="text" placeholder="Jane Smith"
                      value={form.naam} onChange={handleChange} className={inp(!!errors.naam)} autoComplete="name" />
                  </Field>
                  <Field label="Company" icon={<Building2 size={14} className="text-neutral-400" />} error={errors.bedrijf}>
                    <input name="bedrijf" type="text" placeholder="Acme Corp"
                      value={form.bedrijf} onChange={handleChange} className={inp(!!errors.bedrijf)} autoComplete="organization" />
                  </Field>
                </div>

                <div className="grid sm:grid-cols-2 gap-4">
                  <Field label="Email" icon={<Mail size={14} className="text-neutral-400" />} error={errors.email}>
                    <input name="email" type="email" placeholder="jane@company.com"
                      value={form.email} onChange={handleChange} className={inp(!!errors.email)} autoComplete="email" />
                  </Field>
                  <Field label="Phone" icon={<Phone size={14} className="text-neutral-400" />} optional>
                    <input name="telefoon" type="tel" placeholder="+31 6 12345678"
                      value={form.telefoon} onChange={handleChange} className={inp(false)} autoComplete="tel" />
                  </Field>
                </div>

                <Field label="What do you want to automate?" icon={<MessageSquare size={14} className="text-neutral-400" />} error={errors.bericht}>
                  <textarea name="bericht" rows={5}
                    placeholder="Describe briefly which processes cost your team time or are error-prone — document processing, email handling, reporting, CRM updates…"
                    value={form.bericht} onChange={handleChange}
                    className={`${inp(!!errors.bericht)} resize-none`} />
                </Field>

                {serverError && (
                  <div className="flex items-start gap-3 px-4 py-3.5 rounded-xl text-sm"
                    style={{ backgroundColor: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)" }}>
                    <AlertCircle size={16} className="text-red-500 flex-shrink-0 mt-0.5" />
                    <span className="text-red-600 leading-relaxed">{serverError}</span>
                  </div>
                )}

                <button type="submit" disabled={loading}
                  onMouseEnter={() => !loading && setSubmitHover(true)}
                  onMouseLeave={() => setSubmitHover(false)}
                  onMouseDown={() => setSubmitHover(false)}
                  onMouseUp={() => setSubmitHover(true)}
                  className="w-full flex items-center justify-center gap-2 py-4 rounded-full text-[0.9375rem] font-semibold text-white disabled:opacity-60 disabled:cursor-not-allowed mt-1"
                  style={{
                    backgroundColor: submitHover ? "#1d4ed8" : "#2563EB",
                    boxShadow: submitHover ? "0 6px 20px -4px rgba(37,99,235,0.4)" : "0 1px 4px rgba(37,99,235,0.2)",
                    transform: submitHover ? "translateY(-2px)" : "translateY(0)",
                    transition: "background-color 150ms ease, box-shadow 150ms ease, transform 150ms ease",
                  }}>
                  {loading ? <><Spinner />Sending…</> : <>Request Demo <ArrowRight size={16} /></>}
                </button>

                <p className="text-xs text-neutral-400 text-center">
                  No spam. We use your details only to follow up on your request.
                </p>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function SuccessState() {
  const [visible, setVisible] = useState(false);
  useEffect(() => { requestAnimationFrame(() => requestAnimationFrame(() => setVisible(true))); }, []);

  return (
    <div className="flex flex-col items-center text-center py-14 gap-6"
      style={{ opacity: visible ? 1 : 0, transform: visible ? "scale(1) translateY(0px)" : "scale(0.97) translateY(8px)",
        transition: "opacity 500ms cubic-bezier(0.4,0,0.2,1), transform 500ms cubic-bezier(0.4,0,0.2,1)" }}>
      <div className="w-16 h-16 rounded-full flex items-center justify-center"
        style={{ backgroundColor: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)" }}>
        <CheckCircle2 size={30} style={{ color: "#059669" }} />
      </div>
      <div className="w-full max-w-sm rounded-2xl px-6 py-5"
        style={{ backgroundColor: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.18)" }}>
        <p className="text-sm font-semibold text-emerald-700 mb-1">Request received</p>
        <p className="text-sm text-emerald-600 leading-relaxed">We&apos;ll be in touch within 1 business day.</p>
      </div>
      <div>
        <h3 className="text-xl font-semibold text-neutral-900 mb-2">Thank you.</h3>
        <p className="text-sm text-neutral-500 leading-relaxed max-w-xs mx-auto">
          We&apos;ve received your request and will reach out shortly.
        </p>
      </div>
      <a href="/" className="text-sm font-medium text-neutral-400 hover:text-neutral-700 transition-colors duration-150">
        Back to home
      </a>
    </div>
  );
}

function Field({ label, icon, error, optional, children }: {
  label: string; icon?: React.ReactNode; error?: string; optional?: boolean; children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-neutral-700 flex items-center gap-1.5">{icon}{label}</label>
        {optional && <span className="text-xs text-neutral-400">Optional</span>}
      </div>
      {children}
      {error && <p className="text-xs font-medium text-red-500">{error}</p>}
    </div>
  );
}

function Spinner() {
  return (
    <svg className="animate-spin mr-1" width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="6" stroke="rgba(255,255,255,0.3)" strokeWidth="2" />
      <path d="M8 2a6 6 0 0 1 6 6" stroke="white" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function inp(hasError: boolean): string {
  return [
    "w-full px-4 py-2.5 rounded-xl text-sm text-neutral-800 bg-neutral-50 outline-none",
    "transition-all duration-200 placeholder:text-neutral-300 focus:bg-white",
    hasError
      ? "border border-red-300 focus:border-red-400 focus:ring-2 focus:ring-red-100"
      : "border border-neutral-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
  ].join(" ");
}
