import { ScanLine, Inbox, Users, BrainCircuit, Workflow, Bot, Eye } from "lucide-react";

const capabilities = [
  {
    icon: ScanLine,
    number: "01",
    title: "Document Intelligence",
    description:
      "Inversiq processes PDFs, scanned forms, contracts, invoices, and technical documents with production-grade accuracy. Structured extraction, validation against business rules, and downstream routing — without manual review.",
    technical: "Multi-modal LLM pipeline · Custom extraction schemas · Confidence scoring",
  },
  {
    icon: Eye,
    number: "02",
    title: "Computer Vision",
    description:
      "Site inspections, damage assessments, material verification, quality control — Inversiq's vision models are trained on industry-specific imagery to deliver actionable outputs, not just classifications.",
    technical: "Fine-tuned vision models · Defect detection · Measurement extraction",
  },
  {
    icon: Users,
    number: "03",
    title: "CRM & System Integration",
    description:
      "Inversiq writes to every system you already use. No duplicate data entry, no stale records. Every action taken by the platform is reflected in your systems of record in real time.",
    technical: "REST & webhook integrations · Bi-directional sync · Zero migration required",
  },
  {
    icon: BrainCircuit,
    number: "04",
    title: "Decision Engine",
    description:
      "Define your rules and thresholds. Inversiq applies your decision framework consistently, at volume, with full audit trails for every outcome — and escalates only the exceptions that need human attention.",
    technical: "Rule engine + ML ensemble · Explainable decisions · Policy versioning",
  },
  {
    icon: Workflow,
    number: "05",
    title: "Workflow Orchestration",
    description:
      "Inversiq coordinates people, systems, and AI across multi-step processes. Parallel execution, conditional branching, SLA monitoring, and a complete audit trail — built in.",
    technical: "DAG-based execution · Async task queues · SLA monitoring · Full observability",
  },
  {
    icon: Bot,
    number: "06",
    title: "AI Agents",
    description:
      "Autonomous agents that operate across your software stack — reading inputs, applying logic, making decisions, and taking actions without human intervention at every step.",
    technical: "Multi-agent framework · Tool use & API calls · Configurable autonomy levels",
  },
];

export default function WhatWeDo() {
  return (
    <section id="platform" className="py-14 lg:py-24 bg-white">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid lg:grid-cols-2 gap-16 items-start">

          {/* Left: sticky header */}
          <div className="lg:sticky lg:top-32">
            <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-4">
              The Platform
            </p>
            <h2 className="text-4xl lg:text-5xl font-semibold tracking-tight text-foreground leading-tight text-balance mb-6">
              One platform.
              <br />
              <span style={{ color: "#2563EB" }}>Every input.</span>
              <br />
              Fully automated decisions.
            </h2>
            <p className="text-lg text-neutral-500 leading-relaxed mb-8">
              Inversiq is built as a unified AI decision infrastructure layer — not a collection of integrations.
              Every capability shares the same data model, orchestration engine, and business logic framework.
            </p>

            {/* Differentiator box */}
            <div className="inline-flex items-start gap-4 p-5 rounded-2xl w-full"
              style={{ backgroundColor: "rgba(37,99,235,0.04)", border: "1px solid rgba(37,99,235,0.10)" }}>
              <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                style={{ backgroundColor: "#2563EB" }}>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M2 7l3.5 3.5L12 3" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <div>
                <p className="font-semibold text-sm mb-1" style={{ color: "#1d4ed8" }}>
                  Infrastructure, not integration.
                </p>
                <p className="text-sm leading-relaxed" style={{ color: "rgba(37,99,235,0.65)" }}>
                  Inversiq is not built on third-party automation platforms. We develop and own our core AI infrastructure —
                  document intelligence models, orchestration engine, and decision framework.
                </p>
              </div>
            </div>
          </div>

          {/* Right: capabilities */}
          <div className="grid gap-4">
            {capabilities.map((cap) => {
              const Icon = cap.icon;
              return (
                <div key={cap.title}
                  className="group flex items-start gap-5 p-6 bg-white border border-neutral-100 rounded-2xl hover:border-neutral-200 hover:shadow-sm transition-all duration-200">
                  <div className="w-10 h-10 rounded-xl bg-neutral-50 border border-neutral-100 flex items-center justify-center flex-shrink-0 group-hover:bg-neutral-100 transition-colors">
                    <Icon size={18} className="text-neutral-500" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <h3 className="font-semibold text-foreground tracking-tight text-sm">{cap.title}</h3>
                      <span className="text-[10px] font-medium text-neutral-300 bg-neutral-50 border border-neutral-100 px-2 py-0.5 rounded-full">
                        {cap.number}
                      </span>
                    </div>
                    <p className="text-sm text-neutral-500 leading-relaxed mb-2">{cap.description}</p>
                    <p className="text-[11px] font-medium" style={{ color: "rgba(37,99,235,0.5)" }}>{cap.technical}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
