"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  ArrowRight, FileText, Camera, GitMerge, RefreshCw,
  Bot, BarChart3, ShieldCheck, CheckCircle2, XCircle,
  ChevronRight, Eye, AlertTriangle, Lock, Layers,
  Zap, Users, Building2, Truck,
} from "lucide-react";

/* ─── Utilities ───────────────────────────────────────── */

function useReducedMotion() {
  const [r, setR] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setR(mq.matches);
    const h = (e: MediaQueryListEvent) => setR(e.matches);
    mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, []);
  return r;
}

function useReveal(threshold = 0.1) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect(); } },
      { threshold }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, visible };
}

/* ─── Capability sections ─────────────────────────────── */

const CAPABILITIES = [
  {
    anchor: "document-intelligence",
    icon: FileText,
    color: "#3B82F6",
    bg: "bg-white",
    title: "Document Intelligence",
    tagline: "Any document. Any format. Structured, validated output.",
    intro: "Operational industries run on documents that no standard system was built to read. Scanned PDFs, handwritten forms, multi-page contracts, field reports in seven different layouts — Inversiq ingests all of them and returns structured, validated data ready for downstream decisions.",
    what: [
      { label: "Multi-modal extraction", text: "A fine-tuned LLM pipeline reads the document as a whole — understanding context, field relationships and implicit structure — not just running OCR and hoping for the best." },
      { label: "Schema-defined output", text: "You define what fields matter for each document type. Inversiq extracts exactly those fields, nothing more. No mapping step, no post-processing, no spreadsheet glue." },
      { label: "Confidence scoring", text: "Every extracted field carries a confidence score. Outputs that fall below your configured threshold are routed to human review automatically. High-confidence outputs proceed without touching a human queue." },
      { label: "Business rule validation", text: "Extracted data is validated against your rules before leaving the extraction layer — cross-field checks, format constraints, allowable value ranges, regulatory requirements." },
    ],
    useCases: [
      { icon: Building2, label: "Construction", text: "Read inspection reports, building permits, subcontractor invoices and compliance certificates — regardless of which contractor or municipality produced them." },
      { icon: ShieldCheck, label: "Insurance", text: "Process claims forms, medical reports, damage assessments and policy schedules from any insurer or healthcare provider format." },
      { icon: Truck, label: "Logistics", text: "Extract from bills of lading, customs declarations, delivery notes and proof-of-delivery documents across carrier formats." },
      { icon: Users, label: "Field Services", text: "Digitise handwritten field technician reports, service checklists and equipment certificates with production-grade accuracy." },
    ],
    integrations: [
      { layer: "Decision Infrastructure", desc: "Extracted fields feed directly into the rule engine. No manual export, no intermediate database." },
      { layer: "Human Review", desc: "Low-confidence extractions are surfaced with full document context so reviewers correct the right thing — not everything." },
      { layer: "Observability", desc: "Extraction accuracy, throughput and exception rates are tracked in real time across every document type." },
    ],
    specs: ["Multi-modal LLM pipeline", "Custom extraction schemas", "Confidence scoring per field", "Business rule validation", "Multi-language support", "Handwriting & scan recognition", "Batch + real-time processing"],
  },
  {
    anchor: "computer-vision",
    icon: Camera,
    color: "#06B6D4",
    bg: "bg-[#F8FAFC]",
    title: "Computer Vision",
    tagline: "Images and video as structured operational data — not just labels.",
    intro: "A significant share of decisions in construction, insurance and field services are triggered by visual evidence. Generic vision APIs return tags. Inversiq returns structured, business-ready outputs: condition scores, defect classifications, measurements and actionable findings that feed directly into the decision layer.",
    what: [
      { label: "Domain-specific fine-tuning", text: "Models are fine-tuned on industry imagery — cracked concrete, roof damage, meter readings, component defects — not general web images. Domain coverage is what separates useful outputs from generic labels." },
      { label: "Structured classification", text: "Every image produces a structured output schema, not a tag cloud. Defect type, severity, location, confidence — the same fields every time, ready for downstream rules." },
      { label: "Multi-image fusion", text: "Multiple photos of the same site or asset are correlated and fused into a single structured finding. A 12-photo site inspection becomes one decision input, not 12 separate API calls." },
      { label: "Measurement extraction", text: "Area estimates, linear measurements and quantity counts from images — referenced against known scale factors, annotations or document data where available." },
    ],
    useCases: [
      { icon: Building2, label: "Construction", text: "Automate site inspection reporting: classify defect types, estimate repair areas, flag safety non-compliance, all from photos taken by a site supervisor's phone." },
      { icon: ShieldCheck, label: "Insurance", text: "Process damage assessment photos submitted with claims: classify damage severity, identify affected components, estimate repair scope without an adjuster on site." },
      { icon: Truck, label: "Logistics", text: "Verify cargo condition at loading and delivery, detect visible damage, confirm load completeness from dock cameras or driver photos." },
      { icon: Zap, label: "Utilities", text: "Read meter displays, classify infrastructure condition from aerial or ground-level images, flag anomalies for maintenance scheduling." },
    ],
    integrations: [
      { layer: "Document Intelligence", desc: "Vision outputs are fused with document data. A damage photo and an inspection PDF jointly inform a single decision — no manual correlation." },
      { layer: "Decision Infrastructure", desc: "Structured vision outputs feed the rule engine directly: severity scores trigger approval thresholds, defect classifications route to the right workflow." },
      { layer: "Workflow Orchestration", desc: "A failed visual inspection can instantly trigger a contractor notification, schedule a follow-up inspection, or block a payment release." },
    ],
    specs: ["Domain fine-tuned models", "Defect detection & severity scoring", "Measurement extraction", "Multi-image fusion", "Structured output schema", "Confidence per finding", "API & batch ingestion"],
  },
  {
    anchor: "decision-infrastructure",
    icon: GitMerge,
    color: "#8B5CF6",
    bg: "bg-white",
    title: "Decision Infrastructure",
    tagline: "Your business logic, applied consistently at any volume.",
    intro: "This is the core of the Inversiq platform. Business rules, approval thresholds, routing logic and escalation criteria are encoded once — then applied consistently to every input, at any volume, with a full audit trail. Decisions are no longer dependent on the experience or availability of a specific individual.",
    what: [
      { label: "Rule engine + ML ensemble", text: "Deterministic rules handle what you can specify explicitly. ML models handle the cases your rules don't fully cover — edge cases, ambiguous inputs, novel patterns. Both run in the same decision loop." },
      { label: "Multi-signal fusion", text: "A decision can incorporate document extractions, vision outputs, CRM data, historical decisions and external data in a single evaluation. Every signal is weighted according to your configuration." },
      { label: "Threshold configuration", text: "You define the acceptance thresholds, escalation triggers and routing conditions. Inversiq enforces them. When your business rules change, you update the configuration — not the codebase." },
      { label: "Policy versioning", text: "Every rule version is logged. You can see exactly which policy version produced any historical decision — and roll back instantly if a policy change produces unintended outcomes." },
    ],
    useCases: [
      { icon: Building2, label: "Construction", text: "Automatically approve subcontractor invoices within tolerance, escalate disputes, route change orders to the right project manager — based on your rules, consistently." },
      { icon: ShieldCheck, label: "Insurance", text: "Evaluate claims against policy terms, coverage limits and fraud indicators. Accept, reject or escalate with a full explanation of the deciding factors." },
      { icon: Truck, label: "Logistics", text: "Route shipments, flag exceptions, approve carrier invoices against contracted rates, trigger penalty clauses — all without a human making the same calculation repeatedly." },
      { icon: Users, label: "Any vertical", text: "Encode your highest-volume, highest-consistency decisions. Free your team to focus on the exceptions that actually need human judgment." },
    ],
    integrations: [
      { layer: "Document Intelligence", desc: "Receives structured field extractions as decision inputs. No intermediate step required." },
      { layer: "Computer Vision", desc: "Visual findings — severity scores, defect classifications — are decision inputs alongside document data." },
      { layer: "Workflow Orchestration", desc: "Every decision outcome triggers a workflow: approval, rejection, escalation, payment, notification — automatically." },
      { layer: "Observability", desc: "Every decision is logged with its inputs, the rule or model that drove it, and its outcome — searchable and exportable." },
    ],
    specs: ["Rule engine + ML ensemble", "Multi-signal decision fusion", "Configurable thresholds", "Escalation routing", "Explainable outcomes", "Policy versioning & rollback", "Real-time + batch evaluation"],
  },
  {
    anchor: "workflow-orchestration",
    icon: RefreshCw,
    color: "#10B981",
    bg: "bg-[#F8FAFC]",
    title: "Workflow Orchestration",
    tagline: "Decisions become actions across your entire stack — automatically.",
    intro: "A decision without execution is just a recommendation. Inversiq's workflow orchestration layer closes the loop: once a decision is made, the resulting actions happen automatically across your systems. No copy-paste, no manual triggers, no follow-up emails to see if someone acted on the output.",
    what: [
      { label: "DAG-based execution", text: "Workflows are defined as directed acyclic graphs — each step explicit, each dependency clear, each branch condition stated. No hidden control flow, no brittle scripts." },
      { label: "Parallel and conditional branching", text: "Multiple downstream actions can execute simultaneously. Branches follow conditional logic: if invoice amount > threshold AND supplier is flagged, take path A; otherwise, path B." },
      { label: "SLA monitoring", text: "Every workflow step has a configurable time constraint. If a human review task sits unactioned for too long, Inversiq escalates automatically — not after someone notices it's late." },
      { label: "System write-back", text: "Inversiq updates the systems you already use: CRM, ERP, project management, notification platforms, accounting software. One decision, many system updates, zero manual re-entry." },
    ],
    useCases: [
      { icon: Building2, label: "Construction", text: "Invoice approved → update project budget in ERP, notify accounts payable, release payment instruction, log against project cost code. All automatic." },
      { icon: ShieldCheck, label: "Insurance", text: "Claim accepted → update claims system, issue payment instruction, notify claimant, close task in CRM, file documents in DMS. One decision, six system actions." },
      { icon: Truck, label: "Logistics", text: "Delivery confirmed → update shipment status, trigger customer notification, release carrier payment, flag discrepancies for review queue." },
      { icon: Users, label: "Field Services", text: "Inspection completed → generate report, notify client, create follow-up job if defects found, update asset register, file compliance documentation." },
    ],
    integrations: [
      { layer: "Decision Infrastructure", desc: "Every decision outcome is the trigger for a workflow. No polling, no manual handoff." },
      { layer: "AI Agents", desc: "Multi-step, ambiguous tasks are handled by agents operating within the orchestration framework — their actions are steps in the workflow." },
      { layer: "Observability", desc: "Every workflow step is logged: what ran, when, what it produced, what it updated in your systems." },
    ],
    specs: ["DAG-based execution engine", "Parallel & conditional branching", "SLA monitoring & auto-escalation", "CRM / ERP write-back", "Webhook & REST API triggers", "Human task routing & queuing", "Retry logic & error handling"],
  },
  {
    anchor: "ai-agents",
    icon: Bot,
    color: "#F59E0B",
    bg: "bg-white",
    title: "AI Agents",
    tagline: "Autonomous execution across multi-step, ambiguous processes.",
    intro: "Not every operational task fits a deterministic rule. Some require judgment, context-gathering, multi-step reasoning or adaptive responses to unexpected situations. Inversiq agents handle these tasks end-to-end — grounded in your business logic, constrained to your approved systems, with configurable autonomy levels and a full action log.",
    what: [
      { label: "Multi-agent framework", text: "Complex tasks are decomposed across specialised agents — one that reads documents, one that queries your CRM, one that drafts a response — coordinated by an orchestrating agent that manages the overall task." },
      { label: "Configurable autonomy", text: "You decide what agents can do without human approval. Low-risk actions execute automatically. Higher-risk actions surface for approval first. Autonomy boundaries are explicit and auditable." },
      { label: "Tool use and system integration", text: "Agents can call your APIs, read from your databases, write to your CRM, send emails, query external services — scoped to exactly the systems you authorise per deployment." },
      { label: "Long-horizon task execution", text: "Some tasks take hours: gather three quotes, compare against budget, draft a recommendation, get approval, issue the PO. Agents handle the entire sequence, not just one step." },
    ],
    useCases: [
      { icon: Building2, label: "Construction", text: "Agent receives RFQ, reads project specs, queries supplier catalogue, generates three comparable quotes, checks against budget, flags to project manager for approval." },
      { icon: ShieldCheck, label: "Insurance", text: "Agent processes ambiguous claim: reads documents, queries policy database, requests missing evidence, cross-references similar claims, produces recommendation with supporting rationale." },
      { icon: Truck, label: "Logistics", text: "Agent resolves delivery exception: reads delivery note, queries carrier system, contacts depot, reschedules delivery, notifies customer, updates shipment record." },
      { icon: Users, label: "Field Services", text: "Agent handles service escalation: reads fault report, diagnoses issue against knowledge base, schedules engineer, orders parts, updates customer — without a dispatcher in the loop." },
    ],
    integrations: [
      { layer: "Decision Infrastructure", desc: "Agents are grounded by the decision layer — business rules constrain what actions they can take and what outputs are acceptable." },
      { layer: "Workflow Orchestration", desc: "Agent actions are steps in a workflow. Their outputs trigger the same downstream actions as any other decision." },
      { layer: "Observability", desc: "Every agent action is logged — tool calls, reasoning steps, outputs — so you can audit exactly what happened and why." },
    ],
    specs: ["Multi-agent orchestration", "Configurable autonomy levels", "Tool use & API calls", "Long-horizon task execution", "Memory & context management", "Full action audit trail", "Human-in-the-loop approvals"],
  },
  {
    anchor: "observability",
    icon: BarChart3,
    color: "#64748B",
    bg: "bg-[#F8FAFC]",
    title: "Observability",
    tagline: "Complete visibility into every decision, workflow and agent action.",
    intro: "Enterprise deployments require more than performance — they require accountability. Observability in Inversiq is not a dashboard added as an afterthought. It is a cross-cutting infrastructure layer: every platform component emits structured events, and every event is logged, indexed and queryable. Regulators, auditors and operations teams all get what they need.",
    what: [
      { label: "Real-time dashboards", text: "Throughput, exception rates, automation percentages, SLA compliance and confidence distribution — all live. Slice by document type, vertical, time period or individual workflow." },
      { label: "Decision audit logs", text: "Every decision is logged with its full context: the input data, the rule or model that produced the outcome, the confidence level, the operator who reviewed it (if any), and the timestamp. Searchable, filterable, exportable." },
      { label: "Exception and escalation tracking", text: "Know exactly how many decisions required human review, why they were escalated, how long they sat in the queue, and what the reviewer decided. Track reviewer accuracy over time." },
      { label: "Anomaly alerting", text: "Statistical process control over your automation metrics. If extraction accuracy drops, exception rates spike or a workflow starts timing out, you find out before your operations team does." },
    ],
    useCases: [
      { icon: ShieldCheck, label: "Compliance teams", text: "Export a complete audit trail for any time period, any document type, any decision outcome — formatted for regulatory submission." },
      { icon: Building2, label: "Operations teams", text: "Monitor automation rates and exception queues in real time. Identify which document types or rule combinations are generating the most manual review." },
      { icon: Users, label: "Business owners", text: "See the time and cost impact of automation in concrete terms: hours saved per week, documents processed per day, SLA compliance rate." },
      { icon: Zap, label: "Engineering teams", text: "Debug extraction failures, trace workflow errors, inspect individual agent action logs — all from the same interface without needing to query production databases directly." },
    ],
    integrations: [
      { layer: "Every platform layer", desc: "Observability is not scoped to one module. Document Intelligence, Vision, Decisions, Workflows and Agents all emit to the same event stream." },
      { layer: "External monitoring", desc: "Structured events are available via webhook and API so you can push to your existing observability stack: Datadog, Grafana, Splunk." },
      { layer: "Export & reporting", desc: "Audit exports are available on-demand in CSV, JSON and PDF formats with configurable date ranges and filters." },
    ],
    specs: ["Real-time throughput dashboards", "Per-decision audit logs", "Exception & escalation tracking", "SLA compliance reporting", "Anomaly alerting", "Webhook event export", "CSV / JSON / PDF export"],
  },
];

/* ─── Comparison data ─────────────────────────────────── */

const COMPARISON_ROWS = [
  { label: "Document understanding",     them: "Generic extraction, no domain tuning",  us: "Domain-specific models with schema validation" },
  { label: "Decision logic",             them: "Hardcoded rules or manual review",       us: "Rule engine + ML ensemble, versioned" },
  { label: "Cross-signal fusion",        them: "Siloed per tool",                        us: "Documents + images + data fused into one decision" },
  { label: "Workflow execution",         them: "Manual steps after analysis",            us: "Automated actions across your full stack" },
  { label: "Audit & explainability",     them: "Black box outputs",                      us: "Every decision logged, traceable, exportable" },
  { label: "Multi-tenant deployment",    them: "One integration per customer",           us: "Single platform, configurable per vertical" },
  { label: "Compliance posture",         them: "Retrofitted",                            us: "GDPR, EU AI Act embedded in architecture" },
];

/* ─── Governance items ────────────────────────────────── */

const GOVERNANCE = [
  {
    icon: ShieldCheck,
    color: "#3B82F6",
    title: "Confidence Scoring",
    desc: "Every extraction and decision carries a confidence score. Outputs below your configured threshold are held for human review rather than proceeding automatically. You define the risk tolerance.",
  },
  {
    icon: Eye,
    color: "#8B5CF6",
    title: "Audit Trails",
    desc: "Every document, decision, workflow step and agent action is logged with timestamps, inputs, outputs and the rule or model that produced it. Searchable, filterable, exportable.",
  },
  {
    icon: AlertTriangle,
    color: "#F59E0B",
    title: "Human Review",
    desc: "Exceptions and low-confidence outputs are surfaced to the right operator with full context — not just a flag, but the document, the extracted data, and the decision rationale.",
  },
  {
    icon: Layers,
    color: "#10B981",
    title: "Explainability",
    desc: "Decision outputs include the rule or model component that drove each outcome. Operators can inspect why a document was approved, routed or escalated — not just that it was.",
  },
  {
    icon: Lock,
    color: "#06B6D4",
    title: "Decision Governance",
    desc: "Business rules are version-controlled. Policy changes are logged. Rollbacks are instant. You can see exactly which rule version was applied to any historical decision.",
  },
];

/* ─── Anchor IDs in order for URL tracking ───────────── */
const ANCHOR_IDS = CAPABILITIES.map((c) => c.anchor);

/* ═══════════════════════════════════════════════════════ */

export default function PlatformOverviewPage() {
  const reducedMotion = useReducedMotion();

  /* Track active section → update URL hash */
  useEffect(() => {
    const sections = ANCHOR_IDS.map((id) => document.getElementById(id)).filter(Boolean) as HTMLElement[];
    if (!sections.length) return;

    const obs = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (!visible.length) return;
        // Pick the one closest to top of viewport
        const top = visible.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        const id = top.target.id;
        if (id && window.location.hash !== `#${id}`) {
          history.replaceState(null, "", `#${id}`);
        }
      },
      { threshold: 0.25, rootMargin: "-80px 0px -40% 0px" }
    );

    sections.forEach((s) => obs.observe(s));
    return () => obs.disconnect();
  }, []);

  return (
    <div>
      <style>{`
        @keyframes gridFade  { 0%,100%{opacity:.04} 50%{opacity:.08} }
        @keyframes glowPulse { 0%,100%{opacity:.15} 50%{opacity:.25} }
        @keyframes flowDot   { 0%{opacity:0;transform:translateX(-8px)} 20%{opacity:1} 80%{opacity:1} 100%{opacity:0;transform:translateX(8px)} }
        @keyframes dotBlink  { 0%,100%{opacity:1} 50%{opacity:.3} }
      `}</style>

      <HeroSection reducedMotion={reducedMotion} />
      <ArchitectureSection reducedMotion={reducedMotion} />

      {/* Capability anchor sections */}
      {CAPABILITIES.map((cap, i) => (
        <CapabilitySection key={cap.anchor} cap={cap} index={i} />
      ))}

      <WhyInversiqSection />
      <GovernanceSection />
      <CtaSection />
    </div>
  );
}

/* ── 1. Hero ──────────────────────────────────────────── */

function HeroSection({ reducedMotion }: { reducedMotion: boolean }) {
  const [ready, setReady] = useState(false);
  useEffect(() => { const t = setTimeout(() => setReady(true), 60); return () => clearTimeout(t); }, []);

  const fade = (d: number): React.CSSProperties =>
    reducedMotion ? {} : {
      opacity: ready ? 1 : 0,
      transform: ready ? "none" : "translateY(18px)",
      transition: `opacity 600ms ease ${d}ms, transform 600ms ease ${d}ms`,
    };

  return (
    <section className="relative overflow-hidden bg-[#080C14] pt-[108px] lg:pt-[124px]">
      <div className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: "linear-gradient(rgba(59,130,246,0.06) 1px,transparent 1px),linear-gradient(90deg,rgba(59,130,246,0.06) 1px,transparent 1px)",
          backgroundSize: "64px 64px",
          animation: reducedMotion ? "none" : "gridFade 8s ease-in-out infinite",
        }} />
      <div className="absolute pointer-events-none"
        style={{
          top: "-10%", left: "50%", transform: "translateX(-50%)",
          width: "120%", height: "130%",
          background: "radial-gradient(ellipse at 50% 35%, rgba(37,99,235,0.2) 0%, rgba(96,165,250,0.06) 45%, transparent 70%)",
          animation: reducedMotion ? "none" : "glowPulse 7s ease-in-out infinite",
        }} />

      <div className="relative max-w-[1280px] mx-auto px-5 sm:px-6 xl:px-8 py-16 sm:py-20 lg:py-28 text-center">

        {/* Breadcrumb */}
        <div className="flex items-center justify-center gap-2 mb-6 text-[11px] font-medium" style={{ color: "#475569" }}>
          <a href="/" className="hover:text-white transition-colors duration-150">Inversiq</a>
          <ChevronRight size={12} />
          <span style={{ color: "#94A3B8" }}>Platform</span>
        </div>

        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full mb-7"
          style={{
            ...fade(0),
            backgroundColor: "rgba(59,130,246,0.10)", color: "#93C5FD",
            border: "1px solid rgba(59,130,246,0.20)",
            fontSize: "10px", fontWeight: 700, letterSpacing: "0.07em", textTransform: "uppercase",
          }}>
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0"
            style={{ animation: reducedMotion ? "none" : "dotBlink 2s ease-in-out infinite" }} />
          Platform Overview
        </div>

        {/* Headline */}
        <h1 className="font-bold tracking-tight text-white mx-auto mb-5"
          style={{ ...fade(80), fontSize: "clamp(2rem, 5.5vw, 4rem)", lineHeight: 1.06, maxWidth: "800px" }}>
          Decision Infrastructure for<br className="hidden sm:block" /> Operational Industries
        </h1>

        {/* Sub */}
        <p className="mx-auto mb-10"
          style={{ ...fade(160), color: "#94A3B8", fontSize: "clamp(1rem, 2.2vw, 1.125rem)", lineHeight: 1.65, maxWidth: "600px" }}>
          Inversiq transforms documents, images and operational data into governed decisions,
          automated workflows and measurable business outcomes — without replacing the systems your team already uses.
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center" style={fade(240)}>
          <a href="/contact"
            className="flex items-center justify-center gap-2 rounded-full font-semibold text-white transition-all duration-150 hover:opacity-90"
            style={{ padding: "14px 28px", fontSize: "0.9375rem", backgroundColor: "#2563EB", boxShadow: "0 0 0 1px rgba(59,130,246,0.3),0 4px 16px rgba(37,99,235,.4)" }}>
            Request a Demo <ArrowRight size={15} strokeWidth={2.2} />
          </a>
          <a href="/industries/construction"
            className="flex items-center justify-center gap-2 rounded-full font-semibold transition-all duration-150"
            style={{ padding: "14px 28px", fontSize: "0.9375rem", color: "#94A3B8", border: "1px solid rgba(255,255,255,0.12)", backgroundColor: "rgba(255,255,255,0.04)" }}>
            See Construction in Action
          </a>
        </div>

        {/* Layer pills — anchor links */}
        <div className="flex flex-wrap items-center justify-center gap-2 mt-10" style={fade(320)}>
          {CAPABILITIES.map((c) => (
            <a key={c.anchor} href={`#${c.anchor}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-medium transition-all duration-150 hover:opacity-80"
              style={{ backgroundColor: `${c.color}10`, color: c.color, border: `1px solid ${c.color}25` }}>
              <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: c.color }} />
              {c.title}
            </a>
          ))}
        </div>
      </div>

      <div className="absolute bottom-0 left-0 right-0 h-16 pointer-events-none"
        style={{ background: "linear-gradient(transparent,white)" }} />
    </section>
  );
}

/* ── 2. Architecture Overview ─────────────────────────── */

function ArchitectureSection({ reducedMotion }: { reducedMotion: boolean }) {
  const { ref, visible } = useReveal(0.08);

  const inputs = ["PDF / Document", "Site Photo", "Form / Survey", "Email / Inbox", "Field Data", "REST API"];
  const outputs = ["CRM / ERP Update", "Workflow Triggered", "Notification Sent", "Report Generated", "Human Task", "API Callback"];

  const pipeline = [
    { label: "Document Intelligence", color: "#3B82F6", icon: FileText },
    { label: "Computer Vision",       color: "#06B6D4", icon: Camera },
    { label: "Decision Infrastructure",color: "#8B5CF6", icon: GitMerge },
    { label: "Workflow Orchestration", color: "#10B981", icon: RefreshCw },
  ];

  return (
    <section className="py-16 sm:py-20 lg:py-28 bg-white">
      <div className="max-w-[1280px] mx-auto px-5 sm:px-6 xl:px-8">

        <div ref={ref} className="max-w-[640px] mb-12 lg:mb-16"
          style={{ opacity: visible ? 1 : 0, transform: visible ? "none" : "translateY(20px)", transition: "opacity 600ms ease, transform 600ms ease" }}>
          <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: "#2563EB" }}>Architecture</p>
          <h2 className="font-bold tracking-tight text-neutral-900 mb-4"
            style={{ fontSize: "clamp(1.625rem, 3.5vw, 2.5rem)", lineHeight: 1.1 }}>
            How the platform processes information.
          </h2>
          <p className="text-neutral-500 leading-relaxed" style={{ fontSize: "clamp(0.9375rem, 1.8vw, 1.0625rem)" }}>
            Every input — regardless of type — flows through the same decision infrastructure.
            One platform. Consistent governance. Unified audit trail.
          </p>
        </div>

        {/* Desktop diagram */}
        <div className="hidden lg:block"
          style={{ opacity: visible ? 1 : 0, transform: visible ? "none" : "translateY(20px)", transition: "opacity 700ms ease 120ms, transform 700ms ease 120ms" }}>
          <div className="rounded-3xl overflow-hidden border" style={{ border: "1px solid #E2E8F0", backgroundColor: "#F8FAFC" }}>
            <div className="px-6 py-3 border-b flex items-center gap-3" style={{ borderColor: "#E2E8F0", backgroundColor: "white" }}>
              <div className="flex gap-1.5">
                {["#F87171","#FBBF24","#34D399"].map(c => <span key={c} className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: c }} />)}
              </div>
              <span className="text-[11px] font-medium" style={{ color: "#94A3B8" }}>Inversiq Platform — Architecture Overview</span>
            </div>
            <div className="p-8">
              <div className="flex items-center gap-2">
                <div className="flex-shrink-0 w-[150px]">
                  <p className="text-[9px] font-bold uppercase tracking-widest mb-3 text-center" style={{ color: "#94A3B8" }}>Inputs</p>
                  <div className="flex flex-col gap-1.5">
                    {inputs.map(label => (
                      <div key={label} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg"
                        style={{ backgroundColor: "white", border: "1px solid #E2E8F0" }}>
                        <FileText size={9} style={{ color: "#94A3B8", flexShrink: 0 }} />
                        <span className="text-[10px] font-medium" style={{ color: "#64748B" }}>{label}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <ArchArrow color="#3B82F6" reducedMotion={reducedMotion} delay={0} />
                {pipeline.map((step, i) => (
                  <React.Fragment key={step.label}>
                    <a href={`#${CAPABILITIES[i]?.anchor ?? ""}`}
                      className="flex-1 rounded-2xl p-4 text-center transition-opacity duration-150 hover:opacity-80"
                      style={{ background: `linear-gradient(160deg,${step.color}14,${step.color}06)`, border: `1px solid ${step.color}25`, minWidth: "120px" }}>
                      <div className="w-8 h-8 rounded-xl flex items-center justify-center mx-auto mb-2.5"
                        style={{ backgroundColor: `${step.color}18`, border: `1px solid ${step.color}30` }}>
                        <step.icon size={14} style={{ color: step.color }} />
                      </div>
                      <p className="text-[10px] font-bold leading-tight" style={{ color: step.color }}>{step.label}</p>
                    </a>
                    {i < pipeline.length - 1 && (
                      <ArchArrow color={pipeline[i + 1].color} reducedMotion={reducedMotion} delay={(i + 1) * 300} />
                    )}
                  </React.Fragment>
                ))}
                <ArchArrow color="#10B981" reducedMotion={reducedMotion} delay={1200} />
                <div className="flex-shrink-0 w-[150px]">
                  <p className="text-[9px] font-bold uppercase tracking-widest mb-3 text-center" style={{ color: "#059669" }}>Outputs</p>
                  <div className="flex flex-col gap-1.5">
                    {outputs.map(label => (
                      <div key={label} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg"
                        style={{ backgroundColor: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.15)" }}>
                        <CheckCircle2 size={9} style={{ color: "#10B981", flexShrink: 0 }} />
                        <span className="text-[10px] font-medium" style={{ color: "#059669" }}>{label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="mt-5 flex items-center gap-3 px-4 py-3 rounded-xl"
                style={{ backgroundColor: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.15)" }}>
                <BarChart3 size={13} style={{ color: "#94A3B8", flexShrink: 0 }} />
                <p className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "#94A3B8" }}>Observability</p>
                <div className="flex-1 h-px mx-2" style={{ background: "linear-gradient(90deg,rgba(148,163,184,0.2),rgba(148,163,184,0.08))" }} />
                <span className="text-[10px]" style={{ color: "#CBD5E1" }}>Audit trail · Decision logs · SLA monitoring · Anomaly alerts — across every layer</span>
              </div>
            </div>
          </div>
        </div>

        {/* Mobile stack */}
        <div className="flex flex-col gap-3 lg:hidden"
          style={{ opacity: visible ? 1 : 0, transition: "opacity 700ms ease 120ms" }}>
          {CAPABILITIES.slice(0, 4).map((cap, i) => (
            <a key={cap.anchor} href={`#${cap.anchor}`}
              className="rounded-2xl p-4 flex items-center gap-3 transition-opacity duration-150 hover:opacity-80"
              style={{ background: `linear-gradient(135deg,${cap.color}12,${cap.color}05)`, border: `1px solid ${cap.color}25` }}>
              <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{ backgroundColor: `${cap.color}18`, border: `1px solid ${cap.color}30` }}>
                <cap.icon size={16} style={{ color: cap.color }} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-bold" style={{ color: cap.color }}>{cap.title}</p>
                <p className="text-[11px] text-neutral-400 truncate">{cap.tagline}</p>
              </div>
              <ChevronRight size={14} style={{ color: cap.color, opacity: 0.5, flexShrink: 0 }} />
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}

function ArchArrow({ color, reducedMotion, delay }: { color: string; reducedMotion: boolean; delay: number }) {
  return (
    <div className="flex-shrink-0 flex items-center justify-center relative" style={{ width: "36px" }}>
      <div className="absolute left-0 right-0 h-px" style={{ background: `linear-gradient(90deg,transparent,${color}50,${color}50,transparent)` }} />
      {!reducedMotion && (
        <div style={{
          width: "5px", height: "5px", borderRadius: "50%", backgroundColor: color,
          boxShadow: `0 0 5px ${color}`,
          animation: `flowDot 2s ease-in-out ${delay}ms infinite`,
          position: "absolute",
        }} />
      )}
      <div className="relative z-10 w-5 h-5 rounded-full flex items-center justify-center"
        style={{ backgroundColor: `${color}12`, border: `1px solid ${color}30` }}>
        <ArrowRight size={9} style={{ color }} />
      </div>
    </div>
  );
}

/* ── 3. Capability Sections ───────────────────────────── */

type CapabilityDef = typeof CAPABILITIES[number];

function CapabilitySection({ cap, index }: { cap: CapabilityDef; index: number }) {
  const { ref, visible } = useReveal(0.06);
  const isEven = index % 2 === 0;

  return (
    <section
      id={cap.anchor}
      className={isEven ? "bg-white" : "bg-[#F8FAFC]"}
      style={{
        scrollMarginTop: "80px",
        borderTop: "1px solid #F1F5F9",
        paddingTop: "80px",
        paddingBottom: "80px",
      }}
    >
      <div ref={ref} className="max-w-[1280px] mx-auto px-5 sm:px-6 xl:px-8"
        style={{ opacity: visible ? 1 : 0, transform: visible ? "none" : "translateY(24px)", transition: "opacity 600ms ease, transform 600ms ease" }}>

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start gap-5 mb-10 lg:mb-14">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0"
            style={{ backgroundColor: `${cap.color}12`, border: `1px solid ${cap.color}25` }}>
            <cap.icon size={22} style={{ color: cap.color }} />
          </div>
          <div className="flex-1">
            <p className="text-[10px] font-bold uppercase tracking-widest mb-1.5" style={{ color: cap.color }}>
              Platform · {cap.title}
            </p>
            <h2 className="font-bold tracking-tight text-neutral-900 mb-3"
              style={{ fontSize: "clamp(1.5rem, 3vw, 2.25rem)", lineHeight: 1.1 }}>
              {cap.title}
            </h2>
            <p className="text-neutral-500 leading-relaxed max-w-[680px]"
              style={{ fontSize: "clamp(0.9375rem, 1.8vw, 1.0625rem)" }}>
              {cap.intro}
            </p>
          </div>
        </div>

        {/* Main grid */}
        <div className="grid lg:grid-cols-[1fr_340px] gap-8 lg:gap-12 mb-10 lg:mb-12">

          {/* What it does */}
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest mb-5" style={{ color: "#94A3B8" }}>What it does</p>
            <div className="grid sm:grid-cols-2 gap-4">
              {cap.what.map((item) => (
                <div key={item.label} className="rounded-xl p-5"
                  style={{ backgroundColor: `${cap.color}05`, border: `1px solid ${cap.color}15` }}>
                  <p className="text-sm font-semibold mb-2" style={{ color: cap.color }}>{item.label}</p>
                  <p className="text-sm text-neutral-500 leading-relaxed">{item.text}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Specs sidebar */}
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest mb-5" style={{ color: "#94A3B8" }}>Capabilities</p>
            <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #E2E8F0" }}>
              {cap.specs.map((spec, i) => (
                <div key={spec} className="flex items-center gap-3 px-4 py-3"
                  style={{
                    borderTop: i > 0 ? "1px solid #F1F5F9" : "none",
                    backgroundColor: i % 2 === 0 ? "white" : "#FAFBFC",
                  }}>
                  <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: cap.color }} />
                  <span className="text-sm font-medium text-neutral-700">{spec}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Use cases */}
        <div className="mb-10 lg:mb-12">
          <p className="text-[10px] font-bold uppercase tracking-widest mb-5" style={{ color: "#94A3B8" }}>Use cases</p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {cap.useCases.map((uc) => (
              <div key={uc.label} className="rounded-xl p-5 bg-white" style={{ border: "1px solid #E2E8F0" }}>
                <div className="flex items-center gap-2 mb-3">
                  <uc.icon size={14} style={{ color: cap.color, flexShrink: 0 }} />
                  <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: cap.color }}>{uc.label}</span>
                </div>
                <p className="text-sm text-neutral-500 leading-relaxed">{uc.text}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Integrations */}
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest mb-5" style={{ color: "#94A3B8" }}>How it connects</p>
          <div className="flex flex-col sm:flex-row gap-3">
            {cap.integrations.map((intg) => (
              <div key={intg.layer} className="flex-1 rounded-xl p-4"
                style={{ backgroundColor: `${cap.color}06`, border: `1px solid ${cap.color}18` }}>
                <div className="flex items-center gap-2 mb-2">
                  <ArrowRight size={11} style={{ color: cap.color, flexShrink: 0 }} />
                  <span className="text-[11px] font-semibold" style={{ color: cap.color }}>{intg.layer}</span>
                </div>
                <p className="text-xs text-neutral-500 leading-relaxed">{intg.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ── 4. Why Inversiq ─────────────────────────────────── */

function WhyInversiqSection() {
  const { ref, visible } = useReveal(0.08);

  return (
    <section className="py-16 sm:py-20 lg:py-28 bg-white" style={{ borderTop: "1px solid #F1F5F9" }}>
      <div className="max-w-[1280px] mx-auto px-5 sm:px-6 xl:px-8">

        <div ref={ref} className="max-w-[640px] mb-12"
          style={{ opacity: visible ? 1 : 0, transform: visible ? "none" : "translateY(20px)", transition: "opacity 600ms ease, transform 600ms ease" }}>
          <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: "#2563EB" }}>Why Inversiq</p>
          <h2 className="font-bold tracking-tight text-neutral-900 mb-4"
            style={{ fontSize: "clamp(1.625rem, 3.5vw, 2.5rem)", lineHeight: 1.1 }}>
            Point tools vs. decision infrastructure.
          </h2>
          <p className="text-neutral-500 leading-relaxed" style={{ fontSize: "clamp(0.9375rem, 1.8vw, 1.0625rem)" }}>
            Assembling individual AI tools creates integration debt, governance gaps and fragile pipelines.
            Inversiq replaces the assembly with infrastructure.
          </p>
        </div>

        <div className="rounded-2xl overflow-hidden"
          style={{
            opacity: visible ? 1 : 0, transform: visible ? "none" : "translateY(20px)",
            transition: "opacity 650ms ease 100ms, transform 650ms ease 100ms",
            border: "1px solid #E2E8F0",
          }}>
          <div className="grid grid-cols-[1fr_1fr_1fr] bg-neutral-50 border-b" style={{ borderColor: "#E2E8F0" }}>
            <div className="px-5 py-4">
              <p className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "#94A3B8" }}>Capability</p>
            </div>
            <div className="px-5 py-4 border-l" style={{ borderColor: "#E2E8F0", backgroundColor: "rgba(239,68,68,0.03)" }}>
              <div className="flex items-center gap-2">
                <XCircle size={13} style={{ color: "#EF4444" }} />
                <p className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "#EF4444" }}>Assembled AI tools</p>
              </div>
            </div>
            <div className="px-5 py-4 border-l" style={{ borderColor: "#E2E8F0", backgroundColor: "rgba(37,99,235,0.04)" }}>
              <div className="flex items-center gap-2">
                <CheckCircle2 size={13} style={{ color: "#2563EB" }} />
                <p className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "#2563EB" }}>Inversiq</p>
              </div>
            </div>
          </div>
          {COMPARISON_ROWS.map((row, i) => (
            <div key={row.label} className="grid grid-cols-[1fr_1fr_1fr] border-b last:border-b-0"
              style={{ borderColor: "#F1F5F9", backgroundColor: i % 2 === 0 ? "white" : "#FAFBFC" }}>
              <div className="px-5 py-4">
                <p className="text-sm font-semibold text-neutral-800">{row.label}</p>
              </div>
              <div className="px-5 py-4 border-l" style={{ borderColor: "#F1F5F9" }}>
                <p className="text-sm text-neutral-400 leading-relaxed">{row.them}</p>
              </div>
              <div className="px-5 py-4 border-l" style={{ borderColor: "#F1F5F9", backgroundColor: "rgba(37,99,235,0.02)" }}>
                <p className="text-sm font-medium leading-relaxed" style={{ color: "#1d4ed8" }}>{row.us}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── 5. Governance ───────────────────────────────────── */

function GovernanceSection() {
  const { ref, visible } = useReveal(0.08);

  return (
    <section className="py-16 sm:py-20 lg:py-28 bg-[#080C14] relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: "linear-gradient(rgba(59,130,246,0.05) 1px,transparent 1px),linear-gradient(90deg,rgba(59,130,246,0.05) 1px,transparent 1px)",
          backgroundSize: "64px 64px",
        }} />
      <div className="absolute pointer-events-none"
        style={{ top: "50%", left: "50%", transform: "translate(-50%,-50%)", width: "75%", height: "85%",
          background: "radial-gradient(ellipse,rgba(37,99,235,0.11) 0%,transparent 65%)" }} />

      <div className="relative max-w-[1280px] mx-auto px-5 sm:px-6 xl:px-8">
        <div ref={ref} className="max-w-[640px] mb-12"
          style={{ opacity: visible ? 1 : 0, transform: visible ? "none" : "translateY(20px)", transition: "opacity 600ms ease, transform 600ms ease" }}>
          <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: "#3B82F6" }}>Governance</p>
          <h2 className="font-bold tracking-tight text-white mb-4"
            style={{ fontSize: "clamp(1.625rem, 3.5vw, 2.5rem)", lineHeight: 1.1 }}>
            Every decision is governed, explainable and auditable.
          </h2>
          <p className="leading-relaxed" style={{ color: "#64748B", fontSize: "clamp(0.9375rem, 1.8vw, 1.0625rem)" }}>
            Enterprise deployments require more than accuracy. They require accountability.
            Inversiq embeds governance at every layer — not as a post-hoc addition, but as a first-class architectural concern.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4"
          style={{ opacity: visible ? 1 : 0, transform: visible ? "none" : "translateY(20px)", transition: "opacity 650ms ease 120ms, transform 650ms ease 120ms" }}>
          {GOVERNANCE.map((g) => (
            <div key={g.title} className="rounded-2xl p-5 sm:p-6"
              style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
              <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
                style={{ backgroundColor: `${g.color}14`, border: `1px solid ${g.color}25` }}>
                <g.icon size={18} style={{ color: g.color }} />
              </div>
              <h3 className="font-bold text-white mb-2 text-sm">{g.title}</h3>
              <p className="text-xs leading-relaxed" style={{ color: "#64748B" }}>{g.desc}</p>
            </div>
          ))}
        </div>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-x-8 gap-y-3"
          style={{ opacity: visible ? 1 : 0, transition: "opacity 650ms ease 200ms" }}>
          {["GDPR Compliant", "EU AI Act Ready", "SOC 2 Type II", "Role-Based Access", "EU Data Residency"].map(label => (
            <div key={label} className="flex items-center gap-2">
              <ShieldCheck size={12} style={{ color: "#334155" }} />
              <span className="text-[11px] font-medium" style={{ color: "#475569" }}>{label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── 6. CTA ───────────────────────────────────────────── */

function CtaSection() {
  const { ref, visible } = useReveal(0.1);

  return (
    <section className="py-20 sm:py-24 lg:py-32 bg-white">
      <div ref={ref} className="max-w-[760px] mx-auto px-5 sm:px-6 text-center"
        style={{ opacity: visible ? 1 : 0, transform: visible ? "none" : "translateY(20px)", transition: "opacity 600ms ease, transform 600ms ease" }}>

        <p className="text-[10px] font-bold uppercase tracking-widest mb-4" style={{ color: "#2563EB" }}>See it in action</p>
        <h2 className="font-bold tracking-tight text-neutral-900 mb-5"
          style={{ fontSize: "clamp(1.75rem, 4vw, 3rem)", lineHeight: 1.1 }}>
          See Construction in Action
        </h2>
        <p className="mb-8 mx-auto text-neutral-500 leading-relaxed"
          style={{ maxWidth: "480px", fontSize: "clamp(0.9375rem, 1.8vw, 1.0625rem)" }}>
          Construction is the first live vertical on the Inversiq platform. See how Document Intelligence,
          Computer Vision and Decision Infrastructure work together on real operational workflows.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <a href="/industries/construction"
            className="flex items-center justify-center gap-2 rounded-full font-semibold text-white transition-all duration-150 hover:opacity-90"
            style={{ padding: "15px 32px", fontSize: "0.9375rem", backgroundColor: "#2563EB", boxShadow: "0 0 0 1px rgba(37,99,235,0.3),0 4px 16px rgba(37,99,235,.35)" }}>
            Explore Construction Vertical
            <ArrowRight size={15} strokeWidth={2.2} />
          </a>
          <a href="/contact"
            className="flex items-center justify-center gap-2 rounded-full font-semibold transition-all duration-150"
            style={{ padding: "15px 32px", fontSize: "0.9375rem", color: "#64748B", border: "1px solid #E2E8F0", backgroundColor: "#F8FAFC" }}>
            Request a Demo
          </a>
        </div>

        <div className="flex flex-wrap gap-2 justify-center mt-10">
          {CAPABILITIES.map(c => (
            <a key={c.anchor} href={`#${c.anchor}`}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium transition-opacity duration-150 hover:opacity-70"
              style={{ backgroundColor: `${c.color}08`, color: c.color, border: `1px solid ${c.color}18` }}>
              <c.icon size={9} />
              {c.title}
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}
