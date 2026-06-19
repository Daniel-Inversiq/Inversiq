"use client";

import { useEffect, useRef, useState } from "react";
import { FileText, Inbox, Receipt, ArrowRight, type LucideIcon } from "lucide-react";

const cases: {
  icon: LucideIcon;
  tag: string;
  title: string;
  description: string;
  before: { value: string; label: string };
  after: { value: string; label: string };
  steps: string[];
}[] = [
  {
    icon: FileText,
    tag: "Quote Processing",
    title: "From request to sent quote",
    description:
      "A request arrives by email. Inversiq reads the document, applies your pricing logic, updates the CRM, and sends the quote — without a human touching the process.",
    before: { value: "15 min", label: "manual per request" },
    after:  { value: "23 sec", label: "fully automated" },
    steps: ["Email received", "Document parsed", "Quote dispatched"],
  },
  {
    icon: Inbox,
    tag: "Inbox Triage",
    title: "Every message to the right place",
    description:
      "Incoming messages are read, classified by urgency and content, and routed directly to the correct team or workflow — before anyone opens their inbox.",
    before: { value: "2.5 hrs", label: "sorting per day" },
    after:  { value: "0 min",  label: "zero inbox time" },
    steps: ["Message read", "Priority scored", "Routed instantly"],
  },
  {
    icon: Receipt,
    tag: "Invoice Processing",
    title: "Invoices posted without re-entry",
    description:
      "Invoices in any format are extracted, validated against business rules, and posted to your accounting system — including exceptions flagged for review.",
    before: { value: "4 days", label: "average cycle time" },
    after:  { value: "Same day", label: "processed and posted" },
    steps: ["Invoice extracted", "Rules validated", "System updated"],
  },
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

function useInView(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVisible(true); io.disconnect(); } },
      { threshold }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [threshold]);
  return { ref, visible };
}

export default function ResultsSection() {
  const reducedMotion = useReducedMotion();
  const { ref: headerRef, visible: headerVisible } = useInView(0.2);

  return (
    <section id="outcomes" className="py-14 lg:py-24 bg-white">
      <div className="max-w-6xl mx-auto px-6">

        <div ref={headerRef} className="max-w-xl mb-10 lg:mb-16"
          style={reducedMotion ? {} : {
            opacity: headerVisible ? 1 : 0,
            transform: headerVisible ? "translateY(0px)" : "translateY(16px)",
            transition: "opacity 500ms ease, transform 500ms ease",
          }}>
          <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-4">Outcomes</p>
          <h2 className="text-4xl lg:text-5xl font-semibold tracking-tight text-neutral-900 leading-tight text-balance mb-6">
            What happens when work
            <br />
            <span style={{ color: "#2563EB" }}>runs on Inversiq.</span>
          </h2>
          <p className="text-lg text-neutral-500 leading-relaxed">
            Three workflows as Inversiq deploys them. Every implementation is configured to your process,
            but the pattern is always the same: hours become seconds.
          </p>
        </div>

        <div className="grid lg:grid-cols-3 gap-5">
          {cases.map((c, i) => (
            <CaseCard key={c.tag} c={c} index={i} reducedMotion={reducedMotion} />
          ))}
        </div>

        <div className="mt-12 flex items-center gap-4">
          <div className="h-px flex-1" style={{ backgroundColor: "rgba(0,0,0,0.06)" }} />
          <p className="text-sm text-neutral-400 text-center px-4 text-balance">
            Want to see this applied to your specific processes?{" "}
            <a href="/contact" className="font-semibold" style={{ color: "#2563EB" }}>Request a custom demo →</a>
          </p>
          <div className="h-px flex-1" style={{ backgroundColor: "rgba(0,0,0,0.06)" }} />
        </div>
      </div>
    </section>
  );
}

function CaseCard({ c, index, reducedMotion }: { c: typeof cases[number]; index: number; reducedMotion: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [litSteps, setLitSteps] = useState(0);
  const delay = index * 110;

  useEffect(() => {
    if (reducedMotion) { setInView(true); setLitSteps(c.steps.length); return; }
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          c.steps.forEach((_, s) => {
            setTimeout(() => setLitSteps(s + 1), delay + 600 + s * 350);
          });
          io.disconnect();
        }
      },
      { threshold: 0.15 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reducedMotion, delay, c.steps]);

  const Icon = c.icon;

  return (
    <div ref={ref}
      style={{ opacity: inView ? 1 : 0, transform: inView ? "translateY(0px)" : "translateY(20px)",
        transition: reducedMotion ? "none" : `opacity 550ms ease ${delay}ms, transform 550ms ease ${delay}ms` }}
      onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
      <div className="h-full flex flex-col rounded-2xl overflow-hidden"
        style={{
          backgroundColor: "white",
          border: hovered ? "1px solid rgba(37,99,235,0.28)" : "1px solid rgba(0,0,0,0.08)",
          boxShadow: hovered ? "0 8px 28px -6px rgba(37,99,235,0.14), 0 2px 6px rgba(0,0,0,0.04)" : "0 1px 3px rgba(0,0,0,0.04)",
          transform: hovered && !reducedMotion ? "translateY(-4px)" : "translateY(0)",
          transition: "border-color 250ms ease, box-shadow 250ms ease, transform 250ms ease",
        }}>
        <div className="p-7 flex-1">
          <div className="flex items-center gap-2.5 mb-5">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: "rgba(37,99,235,0.06)", border: "1px solid rgba(37,99,235,0.12)" }}>
              <Icon size={16} strokeWidth={1.75} style={{ color: "#2563EB" }} />
            </div>
            <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "#2563EB" }}>
              {c.tag}
            </span>
          </div>
          <h3 className="font-semibold text-neutral-900 tracking-tight mb-2.5 leading-snug">{c.title}</h3>
          <p className="text-sm text-neutral-500 leading-relaxed mb-6">{c.description}</p>

          {/* Animated flow */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {c.steps.map((step, s) => {
              const lit = s < litSteps;
              return (
                <div key={step} className="flex items-center gap-1.5">
                  <span className="text-[11px] font-medium px-2 py-1 rounded-md whitespace-nowrap"
                    style={{
                      backgroundColor: lit ? "rgba(37,99,235,0.07)" : "#f5f5f5",
                      color: lit ? "#2563EB" : "#a3a3a3",
                      border: lit ? "1px solid rgba(37,99,235,0.16)" : "1px solid rgba(0,0,0,0.05)",
                      transition: "all 320ms ease",
                    }}>
                    {step}
                  </span>
                  {s < c.steps.length - 1 && (
                    <ArrowRight size={11} style={{ color: lit ? "#2563EB" : "#d4d4d4", opacity: lit ? 0.7 : 1, transition: "color 320ms ease", flexShrink: 0 }} />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Before / after */}
        <div className="grid grid-cols-2" style={{ borderTop: "1px solid rgba(0,0,0,0.06)" }}>
          <div className="px-6 py-4" style={{ backgroundColor: "#fafafa" }}>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-neutral-400 mb-1">Before</p>
            <p className="text-lg font-bold text-neutral-400 line-through decoration-2 leading-tight">{c.before.value}</p>
            <p className="text-[11px] text-neutral-400 mt-0.5">{c.before.label}</p>
          </div>
          <div className="px-6 py-4"
            style={{ backgroundColor: "rgba(37,99,235,0.04)", borderLeft: "1px solid rgba(37,99,235,0.1)" }}>
            <p className="text-[10px] font-semibold uppercase tracking-wider mb-1" style={{ color: "#2563EB" }}>With Inversiq</p>
            <p className="text-lg font-bold leading-tight" style={{ color: "#2563EB" }}>{c.after.value}</p>
            <p className="text-[11px] mt-0.5" style={{ color: "rgba(37,99,235,0.6)" }}>{c.after.label}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
