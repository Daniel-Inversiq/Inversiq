"use client";

import { useState } from "react";
import { ArrowRight } from "lucide-react";

const verticals = [
  {
    tag: "Live",
    tagColor: { bg: "rgba(16,185,129,0.10)", text: "#059669" },
    name: "Construction",
    headline: "Construction operations, automated.",
    description:
      "From damage assessments and inspection reports to contractor coordination and project documentation — Inversiq processes the documents and images that construction workflows depend on.",
    useCases: [
      "Damage assessment automation",
      "Inspection report processing",
      "Contractor quote validation",
      "Project document extraction",
      "Compliance documentation routing",
    ],
    cta: { label: "Explore Construction", href: "/industries/construction" },
    available: true,
  },
  {
    tag: "Coming Soon",
    tagColor: { bg: "rgba(0,0,0,0.05)", text: "#a3a3a3" },
    name: "Insurance",
    headline: "Claims intelligence at scale.",
    description:
      "Policy documents, loss assessments, photo evidence, and claims forms — unified into a single automated processing pipeline. Faster settlements, fewer errors, full audit trail.",
    useCases: [
      "Claims intake automation",
      "Loss assessment processing",
      "Photo evidence analysis",
      "Policy document extraction",
      "Fraud signal detection",
    ],
    cta: { label: "Join Waitlist", href: "/contact" },
    available: false,
  },
  {
    tag: "Coming Soon",
    tagColor: { bg: "rgba(0,0,0,0.05)", text: "#a3a3a3" },
    name: "Logistics",
    headline: "Documents that move as fast as your freight.",
    description:
      "BOLs, CMRs, customs documents, delivery confirmations — Inversiq processes and validates logistics documentation in real time, eliminating manual processing bottlenecks at every node.",
    useCases: [
      "Bill of lading processing",
      "Customs document validation",
      "Delivery confirmation routing",
      "Exception handling workflows",
      "Carrier compliance checks",
    ],
    cta: { label: "Join Waitlist", href: "/contact" },
    available: false,
  },
  {
    tag: "Coming Soon",
    tagColor: { bg: "rgba(0,0,0,0.05)", text: "#a3a3a3" },
    name: "Field Services",
    headline: "Intelligence at the point of service.",
    description:
      "Work orders, field inspection reports, maintenance logs, and service confirmations — structured and routed automatically from the field to back-office systems without manual re-entry.",
    useCases: [
      "Work order processing",
      "Field report extraction",
      "Asset condition assessment",
      "Service confirmation routing",
      "Maintenance log analysis",
    ],
    cta: { label: "Join Waitlist", href: "/contact" },
    available: false,
  },
];

export default function IndustryVerticals() {
  const [active, setActive] = useState(0);
  const v = verticals[active];

  return (
    <section id="industries" className="py-14 lg:py-24 bg-white">
      <div className="max-w-6xl mx-auto px-6">

        {/* Header */}
        <div className="max-w-2xl mb-12 lg:mb-16">
          <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-4">Industries</p>
          <h2 className="text-4xl lg:text-5xl font-semibold tracking-tight text-neutral-900 leading-tight text-balance mb-6">
            Built for the industries
            <br />
            <span style={{ color: "#2563EB" }}>underserved by software.</span>
          </h2>
          <p className="text-lg text-neutral-500 leading-relaxed">
            Inversiq&apos;s platform is deployable across any workflow-intensive industry.
            We begin where the complexity is highest and the automation gap is largest.
          </p>
        </div>

        <div className="grid lg:grid-cols-[280px_1fr] gap-6 lg:gap-10">

          {/* Tab list */}
          <div className="flex flex-row lg:flex-col gap-2 overflow-x-auto lg:overflow-visible pb-2 lg:pb-0">
            {verticals.map((vert, i) => (
              <button key={vert.name} onClick={() => setActive(i)}
                className="flex-shrink-0 text-left px-4 py-3 rounded-xl transition-all duration-200"
                style={active === i
                  ? { backgroundColor: "rgba(37,99,235,0.06)", border: "1px solid rgba(37,99,235,0.18)" }
                  : { backgroundColor: "transparent", border: "1px solid transparent" }}>
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-sm font-semibold"
                    style={{ color: active === i ? "#1d4ed8" : "#404040" }}>{vert.name}</span>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                    style={{ backgroundColor: vert.tagColor.bg, color: vert.tagColor.text }}>
                    {vert.tag}
                  </span>
                </div>
              </button>
            ))}

            {/* Expansion indicator */}
            <div className="hidden lg:flex items-center gap-3 px-4 py-3 mt-4">
              <div className="h-px flex-1 bg-neutral-100" />
              <p className="text-[11px] text-neutral-400 whitespace-nowrap">More verticals in 2025–2026</p>
            </div>
          </div>

          {/* Detail panel */}
          <div key={v.name} className="rounded-2xl p-8 lg:p-10"
            style={{ backgroundColor: "#FAFAFA", border: "1px solid rgba(0,0,0,0.07)" }}>

            <div className="flex items-start justify-between gap-4 mb-6">
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-widest"
                  style={{ color: v.available ? "#059669" : "#a3a3a3" }}>
                  {v.tag}
                </span>
                <h3 className="text-2xl lg:text-3xl font-semibold tracking-tight text-neutral-900 mt-1 leading-snug">
                  {v.headline}
                </h3>
              </div>
            </div>

            <p className="text-base text-neutral-500 leading-relaxed mb-8">{v.description}</p>

            {/* Use cases */}
            <div className="mb-8">
              <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-4">Use cases</p>
              <div className="grid sm:grid-cols-2 gap-2">
                {v.useCases.map((uc) => (
                  <div key={uc} className="flex items-center gap-2.5">
                    <div className="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: "rgba(37,99,235,0.08)" }}>
                      <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                        <path d="M1.5 4l1.5 1.5 3.5-3.5" stroke="#2563EB" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </div>
                    <span className="text-sm text-neutral-600">{uc}</span>
                  </div>
                ))}
              </div>
            </div>

            <a href={v.cta.href}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold text-white transition-all duration-150 hover:opacity-90 active:scale-[0.98]"
              style={{ backgroundColor: v.available ? "#2563EB" : "#404040" }}>
              {v.cta.label}
              <ArrowRight size={14} />
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
