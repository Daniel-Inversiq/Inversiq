"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowRight, MapPin, Banknote, Code2, Users,
  Briefcase, Clock, ChevronDown, ChevronUp,
} from "lucide-react";

function useReveal(threshold = 0.12) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); obs.disconnect(); } },
      { threshold }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, visible };
}

const VALUES = [
  { label: "Technical depth over headcount",  desc: "We hire for capability, not scale. Small teams solving hard problems." },
  { label: "Industry problems, not toy problems", desc: "Real-world AI deployment in operational environments that matter." },
  { label: "Ownership from day one",          desc: "You ship to production. You own the outcome. No internal agencies." },
  { label: "Remote-first, Europe-based",      desc: "Async by default. In-person when it counts." },
];

const ROLES = [
  {
    title: "AI/ML Engineer",
    icon: Code2,
    color: "#3B82F6",
    location: "Amsterdam / Hybrid",
    compensation: "€55,000 – €85,000",
    compensationNote: null,
    workOn: [
      "Document Intelligence",
      "Computer Vision",
      "ML Pipelines",
      "Evaluation Systems",
      "Decision Intelligence",
      "Agent Performance Optimization",
    ],
    requirements: [
      "Python",
      "Machine Learning",
      "LLM experience",
      "Production AI systems",
    ],
    benefits: [
      "Flexible working",
      "Learning budget",
      "High ownership",
      "Direct impact on product direction",
    ],
  },
  {
    title: "Full-Stack Platform Engineer",
    icon: Briefcase,
    color: "#8B5CF6",
    location: "Amsterdam / Hybrid",
    compensation: "€55,000 – €90,000",
    compensationNote: null,
    workOn: [
      "Multi-tenant SaaS architecture",
      "Workflow orchestration",
      "FastAPI",
      "Observability",
      "Product infrastructure",
      "Platform scalability",
    ],
    requirements: [
      "Python",
      "API design",
      "Cloud infrastructure",
      "Frontend experience",
      "Product mindset",
    ],
    benefits: [
      "Flexible working",
      "Learning budget",
      "Direct access to founders",
      "High ownership",
    ],
  },
  {
    title: "Founding Account Executive",
    icon: Users,
    color: "#10B981",
    location: "Amsterdam / Hybrid",
    compensation: "€45,000 – €70,000 base",
    compensationNote: "+ commission · future equity potential",
    workOn: [
      "Customer acquisition",
      "Enterprise sales",
      "Partnerships",
      "Customer discovery",
      "Go-to-market execution",
      "Revenue growth",
    ],
    requirements: [
      "B2B SaaS sales experience",
      "Strong communication skills",
      "Entrepreneurial mindset",
      "Comfortable selling technical products",
    ],
    benefits: [
      "Performance-based upside",
      "Flexible working",
      "Direct impact on company growth",
      "Potential future equity participation",
    ],
  },
];

export default function Careers() {
  const header = useReveal();
  const roles  = useReveal(0.08);

  return (
    <section id="careers" className="bg-neutral-50 py-16 sm:py-20 lg:py-28"
      style={{ borderTop: "1px solid #E2E8F0" }}>
      <div className="max-w-[1280px] mx-auto px-5 sm:px-6 xl:px-8">

        {/* ── Culture values + intro copy ── */}
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-20 items-start mb-16 lg:mb-24">

          {/* Left */}
          <div ref={header.ref}
            style={{ opacity: header.visible ? 1 : 0, transform: header.visible ? "none" : "translateY(20px)", transition: "opacity 600ms ease, transform 600ms ease" }}>
            <p className="text-[10px] font-bold uppercase tracking-widest mb-4" style={{ color: "#2563EB" }}>Careers</p>
            <h2 className="font-bold tracking-tight text-neutral-900 mb-5"
              style={{ fontSize: "clamp(1.75rem, 3.8vw, 3rem)", lineHeight: 1.1 }}>
              Build the infrastructure
              <br />
              <span style={{ color: "#2563EB" }}>that runs operational industries.</span>
            </h2>
            <p className="text-neutral-500 leading-relaxed mb-4" style={{ fontSize: "clamp(0.9375rem, 1.8vw, 1.0625rem)" }}>
              Inversiq is at an early and consequential stage. The decisions we make now —
              architectural, product, go-to-market — will define what kind of company we become.
            </p>
            <p className="text-neutral-500 leading-relaxed mb-8" style={{ fontSize: "clamp(0.875rem, 1.6vw, 1rem)" }}>
              We are looking for engineers, researchers, and operators who want to work on hard problems:
              real-world AI deployment, multi-modal document understanding, large-scale workflow orchestration,
              and vertical market expansion.
            </p>
            <a href="#future-roles"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-full text-sm font-semibold text-white transition-all duration-150 hover:opacity-90 active:scale-[0.98]"
              style={{ backgroundColor: "#2563EB" }}>
              See Future Roles
              <ArrowRight size={14} />
            </a>
          </div>

          {/* Right: values */}
          <div className="flex flex-col gap-3"
            style={{ opacity: header.visible ? 1 : 0, transform: header.visible ? "none" : "translateY(20px)", transition: "opacity 600ms ease 100ms, transform 600ms ease 100ms" }}>
            {VALUES.map((v) => (
              <div key={v.label} className="flex items-start gap-4 p-5 rounded-2xl bg-white"
                style={{ border: "1px solid #E2E8F0" }}>
                <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                  style={{ backgroundColor: "rgba(37,99,235,0.07)", border: "1px solid rgba(37,99,235,0.12)" }}>
                  <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "#2563EB" }} />
                </div>
                <div>
                  <p className="text-sm font-semibold text-neutral-900 mb-0.5">{v.label}</p>
                  <p className="text-xs text-neutral-500 leading-relaxed">{v.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Future roles ── */}
        <div id="future-roles" ref={roles.ref}
          style={{ opacity: roles.visible ? 1 : 0, transform: roles.visible ? "none" : "translateY(24px)", transition: "opacity 650ms ease, transform 650ms ease" }}>

          {/* Section header */}
          <div className="max-w-[640px] mb-10">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full mb-5"
              style={{ backgroundColor: "rgba(0,0,0,0.04)", border: "1px solid rgba(0,0,0,0.08)" }}>
              <Clock size={11} style={{ color: "#94A3B8" }} />
              <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "#94A3B8" }}>
                Not actively hiring
              </span>
            </div>
            <h3 className="font-bold tracking-tight text-neutral-900 mb-4"
              style={{ fontSize: "clamp(1.5rem, 3vw, 2.25rem)", lineHeight: 1.1 }}>
              Help Build the Future of Operational AI
            </h3>
            <p className="text-neutral-500 leading-relaxed" style={{ fontSize: "clamp(0.9375rem, 1.6vw, 1rem)" }}>
              We&apos;re not actively hiring yet, but we&apos;re always interested in meeting exceptional engineers,
              researchers and operators who want to help build the next generation of AI-native infrastructure.
            </p>
          </div>

          {/* Role cards */}
          <div className="grid lg:grid-cols-3 gap-5">
            {ROLES.map((role, i) => (
              <RoleCard key={role.title} role={role} delay={i * 80} visible={roles.visible} />
            ))}
          </div>

          {/* Bottom note */}
          <div className="mt-10 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 p-5 sm:p-6 rounded-2xl"
            style={{ backgroundColor: "rgba(37,99,235,0.04)", border: "1px solid rgba(37,99,235,0.12)" }}>
            <div>
              <p className="text-sm font-semibold text-neutral-800 mb-1">Interested in joining early?</p>
              <p className="text-xs text-neutral-500 leading-relaxed max-w-md">
                If any of these roles match your profile, reach out via our contact form.
                We&apos;ll keep your details on file for when we begin hiring.
              </p>
            </div>
            <a href="/contact"
              className="flex-shrink-0 inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold text-white transition-all duration-150 hover:opacity-90"
              style={{ backgroundColor: "#2563EB" }}>
              Get in touch
              <ArrowRight size={13} />
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ── Role card with expand/collapse on mobile ── */
function RoleCard({
  role,
  delay,
  visible,
}: {
  role: typeof ROLES[number];
  delay: number;
  visible: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "none" : "translateY(16px)",
        transition: `opacity 500ms ease ${delay}ms, transform 500ms ease ${delay}ms`,
      }}>
      <div className="rounded-2xl bg-white h-full flex flex-col"
        style={{ border: "1px solid #E2E8F0", boxShadow: "0 1px 6px rgba(0,0,0,0.05)" }}>

        {/* Card header */}
        <div className="p-5 sm:p-6 flex-1 flex flex-col">
          <div className="flex items-start justify-between gap-3 mb-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{ backgroundColor: `${role.color}10`, border: `1px solid ${role.color}25` }}>
                <role.icon size={18} style={{ color: role.color }} />
              </div>
              <div>
                <h4 className="font-bold text-neutral-900 text-sm leading-snug">{role.title}</h4>
                <div className="flex items-center gap-1.5 mt-1">
                  <MapPin size={10} style={{ color: "#94A3B8" }} />
                  <span className="text-[11px]" style={{ color: "#94A3B8" }}>{role.location}</span>
                </div>
              </div>
            </div>
            {/* Coming soon badge */}
            <span className="flex-shrink-0 px-2.5 py-1 rounded-full text-[10px] font-semibold"
              style={{ backgroundColor: "rgba(0,0,0,0.04)", color: "#94A3B8", border: "1px solid rgba(0,0,0,0.08)", whiteSpace: "nowrap" }}>
              Coming Soon
            </span>
          </div>

          {/* Compensation */}
          <div className="flex items-start gap-2 mb-5 p-3 rounded-xl"
            style={{ backgroundColor: "#F8FAFC", border: "1px solid #E2E8F0" }}>
            <Banknote size={13} style={{ color: "#64748B", flexShrink: 0, marginTop: "1px" }} />
            <div>
              <span className="text-xs font-semibold text-neutral-800">{role.compensation}</span>
              {role.compensationNote && (
                <p className="text-[10px] text-neutral-500 mt-0.5">{role.compensationNote}</p>
              )}
            </div>
          </div>

          {/* Work on */}
          <div className="mb-4">
            <p className="text-[10px] font-bold uppercase tracking-widest mb-2.5" style={{ color: "#94A3B8" }}>
              What you&apos;ll work on
            </p>
            <div className="flex flex-wrap gap-1.5">
              {role.workOn.map((item) => (
                <span key={item} className="px-2 py-1 rounded-lg text-[11px] font-medium"
                  style={{ backgroundColor: `${role.color}08`, color: role.color, border: `1px solid ${role.color}20` }}>
                  {item}
                </span>
              ))}
            </div>
          </div>

          {/* Requirements — always visible on desktop, collapsible on mobile */}
          <div className={expanded ? "block" : "hidden lg:block"}>
            <div className="mb-4">
              <p className="text-[10px] font-bold uppercase tracking-widest mb-2.5" style={{ color: "#94A3B8" }}>
                We&apos;re looking for
              </p>
              <ul className="flex flex-col gap-1.5">
                {role.requirements.map((req) => (
                  <li key={req} className="flex items-center gap-2 text-xs text-neutral-600">
                    <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ backgroundColor: "#CBD5E1" }} />
                    {req}
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest mb-2.5" style={{ color: "#94A3B8" }}>
                Benefits
              </p>
              <ul className="flex flex-col gap-1.5">
                {role.benefits.map((b) => (
                  <li key={b} className="flex items-center gap-2 text-xs text-neutral-600">
                    <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: "#10B981" }} />
                    {b}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Toggle on mobile */}
          <button
            className="mt-4 flex items-center gap-1.5 text-[11px] font-semibold lg:hidden transition-colors duration-150"
            style={{ color: "#94A3B8" }}
            onClick={() => setExpanded((v) => !v)}>
            {expanded ? <><ChevronUp size={13} /> Less detail</> : <><ChevronDown size={13} /> Requirements & benefits</>}
          </button>
        </div>

        {/* Card footer */}
        <div className="px-5 sm:px-6 py-4 border-t flex items-center justify-between"
          style={{ borderColor: "#F1F5F9" }}>
          <span className="text-[11px] font-medium" style={{ color: "#CBD5E1" }}>Future Opportunity</span>
          <a href="/contact"
            className="flex items-center gap-1.5 text-[11px] font-semibold transition-colors duration-150"
            style={{ color: "#2563EB" }}>
            Express interest
            <ArrowRight size={11} />
          </a>
        </div>
      </div>
    </div>
  );
}
