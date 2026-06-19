"use client";

import { useState } from "react";
import { Plus, Minus } from "lucide-react";

const faqs = [
  {
    question: "How quickly can Inversiq go live?",
    answer:
      "Most deployments go live within 3 to 6 weeks, depending on process complexity and the number of system integrations. We configure, test, and validate against real data before anything runs in production.",
  },
  {
    question: "Does Inversiq work with our existing software?",
    answer:
      "Yes. Inversiq integrates with the systems you already use — CRMs, mailboxes, ERPs, field tools, internal platforms. No migration, no replacement. Your team keeps working the way they work.",
  },
  {
    question: "Is this an AI chatbot or assistant?",
    answer:
      "No. Inversiq is an AI decision infrastructure platform — it processes documents, applies business logic, makes decisions, and takes actions in your systems. It does not generate conversational responses. It performs operational work.",
  },
  {
    question: "Can you build autonomous AI Agents?",
    answer:
      "Yes. We build agents that independently execute multi-step workflows: retrieving information, evaluating it against rules, making decisions, and triggering actions — without human intervention at every step.",
  },
  {
    question: "Do we need to change our processes for Inversiq?",
    answer:
      "No. We analyse your current workflows and configure Inversiq around them. The platform adapts to how you operate — your team does not need to change how they work.",
  },
  {
    question: "What does an implementation cost?",
    answer:
      "It depends on scope. After an initial assessment, we provide a concrete proposal with expected ROI. We only recommend implementations where the return is clear and measurable.",
  },
  {
    question: "How does Inversiq handle data security?",
    answer:
      "Inversiq is built to GDPR, EU AI Act, and industry-specific compliance requirements. We use secure infrastructure, role-based access controls, and full audit logging. Your data remains yours — always.",
  },
  {
    question: "Is Inversiq a software company or a consultancy?",
    answer:
      "Inversiq is an AI platform company. We build and own the Inversiq platform — a multi-tenant AI decision infrastructure deployable across industries. Implementation services exist to ensure production success, not as the primary business model.",
  },
];

export default function FAQSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <section className="py-14 lg:py-16 bg-neutral-50">
      <div className="max-w-6xl mx-auto px-6">
        <div className="max-w-xl mb-10 lg:mb-16">
          <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-4">FAQ</p>
          <h2 className="text-4xl lg:text-5xl font-semibold tracking-tight text-neutral-900 leading-tight text-balance">
            Common questions.
          </h2>
        </div>

        <div className="max-w-3xl">
          {faqs.map((faq, i) => {
            const isOpen = openIndex === i;
            return (
              <div key={i} className="border-b" style={{ borderColor: "rgba(0,0,0,0.08)" }}>
                <button onClick={() => setOpenIndex(isOpen ? null : i)}
                  className="w-full flex items-center justify-between gap-6 py-6 text-left group"
                  aria-expanded={isOpen}>
                  <span className="text-[0.9375rem] font-medium leading-snug transition-colors duration-150"
                    style={{ color: isOpen ? "#2563EB" : "#0a0a0a" }}>
                    {faq.question}
                  </span>
                  <span className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center transition-all duration-200"
                    style={isOpen ? { backgroundColor: "#2563EB" } : { backgroundColor: "rgba(0,0,0,0.06)" }}>
                    {isOpen
                      ? <Minus size={13} color="white" strokeWidth={2.5} />
                      : <Plus size={13} color="#525252" strokeWidth={2.5} />}
                  </span>
                </button>
                <div className="overflow-hidden transition-all duration-300 ease-in-out"
                  style={{ maxHeight: isOpen ? "250px" : "0px" }}>
                  <p className="text-sm text-neutral-500 leading-relaxed pb-6 pr-12">{faq.answer}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
