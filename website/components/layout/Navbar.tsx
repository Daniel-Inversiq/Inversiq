"use client";

import { useState, useEffect, useRef } from "react";
import { Menu, X, ArrowRight, ChevronDown, MoveRight } from "lucide-react";

const platformLinks = [
  { label: "Document Intelligence",  desc: "Extract structured data from any document",       href: "/platform#document-intelligence" },
  { label: "Computer Vision",        desc: "Site inspections and damage assessments at scale", href: "/platform#computer-vision" },
  { label: "Decision Infrastructure",desc: "Business logic that scales without manual review", href: "/platform#decision-infrastructure" },
  { label: "Workflow Orchestration", desc: "Coordinate humans, systems, and AI",              href: "/platform#workflow-orchestration" },
  { label: "AI Agents",              desc: "Autonomous execution across your systems",         href: "/platform#ai-agents" },
  { label: "Observability",          desc: "Full audit trail of every automated decision",     href: "/platform#observability" },
];

const industryLive = [
  { label: "Construction", href: "/industries/construction" },
];
const industryComingSoon = [
  "Real Estate",
  "Insurance",
  "Logistics",
  "Legal",
  "Accounting",
  "Field Services",
  "Industrial Operations",
];

const companyLinks = [
  { label: "About",    href: "/#about" },
  { label: "Careers",  href: "/#careers" },
  { label: "Contact",  href: "/contact" },
];

export default function Navbar() {
  const [scrolled, setScrolled]         = useState(false);
  const [mobileOpen, setMobileOpen]     = useState(false);
  const [platformOpen, setPlatformOpen] = useState(false);
  const [industryOpen, setIndustryOpen] = useState(false);
  const [companyOpen, setCompanyOpen]   = useState(false);
  const [barDismissed, setBarDismissed] = useState(true); // start hidden, read from storage

  useEffect(() => {
    setBarDismissed(sessionStorage.getItem("ann-bar-dismissed") === "1");
  }, []);

  function dismissBar(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    sessionStorage.setItem("ann-bar-dismissed", "1");
    setBarDismissed(true);
  }

  const platformRef = useRef<HTMLDivElement>(null);
  const industryRef = useRef<HTMLDivElement>(null);
  const companyRef  = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 16);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Close dropdowns on outside click
  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (platformRef.current && !platformRef.current.contains(e.target as Node)) setPlatformOpen(false);
      if (industryRef.current && !industryRef.current.contains(e.target as Node)) setIndustryOpen(false);
      if (companyRef.current  && !companyRef.current.contains(e.target as Node))  setCompanyOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function closeAll() {
    setPlatformOpen(false);
    setIndustryOpen(false);
    setCompanyOpen(false);
  }

  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 bg-white"
      style={{
        borderBottom: scrolled
          ? "1px solid rgba(0,0,0,0.08)"
          : "1px solid rgba(0,0,0,0.06)",
        boxShadow: scrolled
          ? "0 1px 12px rgba(0,0,0,0.06)"
          : "none",
        transition: "box-shadow 200ms ease, border-color 200ms ease",
      }}
    >
      {/* Announcement bar */}
      <a
        href="/platform"
        className="group relative flex items-center justify-center gap-2.5 w-full px-4 sm:px-6 transition-opacity duration-150 hover:opacity-90"
        style={{
          minHeight: "40px",
          backgroundColor: "#0F172A",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        {/* Mobile text */}
        <span className="sm:hidden text-[11.5px] font-medium leading-snug tracking-[-0.01em] text-center"
          style={{ color: "#F1F5F9" }}>
          Building decision infrastructure for operational industries.
        </span>

        {/* Desktop text */}
        <span className="hidden sm:inline text-[12.5px] font-medium leading-none tracking-[-0.01em] whitespace-nowrap"
          style={{ color: "#F1F5F9" }}>
          Now building the next generation of decision infrastructure for operational industries.
        </span>

        {/* "Learn →" on mobile, "Learn More →" on sm+ */}
        <span className="inline-flex items-center gap-1 font-semibold flex-shrink-0 text-[11px] sm:text-[12.5px]"
          style={{ color: "#3B82F6" }}>
          <span className="sm:hidden">Learn</span>
          <span className="hidden sm:inline">Learn More</span>
          <MoveRight size={11} strokeWidth={2.2} className="transition-transform duration-150 group-hover:translate-x-0.5" />
        </span>
      </a>

      <nav className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between gap-8">

        {/* Logo */}
        <a href="/" className="flex items-center gap-2.5 shrink-0">
          <LogoMark />
          <span className="font-semibold tracking-tight text-[1.0625rem] text-neutral-900">
            Inversiq
          </span>
        </a>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-1 flex-1 justify-center">

          {/* Platform dropdown */}
          <div ref={platformRef} className="relative">
            <button
              onClick={() => { setPlatformOpen(!platformOpen); setIndustryOpen(false); setCompanyOpen(false); }}
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm font-medium text-neutral-600 hover:text-neutral-900 hover:bg-neutral-50 transition-colors duration-150"
            >
              Platform
              <ChevronDown size={13} strokeWidth={2} className={`transition-transform duration-200 ${platformOpen ? "rotate-180" : ""}`} />
            </button>
            {platformOpen && (
              <div
                className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-72 bg-white rounded-2xl shadow-xl border border-neutral-100 p-2"
                style={{ boxShadow: "0 8px 32px -4px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)" }}
              >
                <a
                  href="/platform"
                  onClick={closeAll}
                  className="flex items-center justify-between px-3 py-2.5 mb-1 rounded-xl hover:bg-blue-50 transition-colors duration-150 group border-b border-neutral-100"
                >
                  <span className="text-sm font-semibold text-blue-600">Platform Overview</span>
                  <ArrowRight size={12} className="text-blue-400" />
                </a>
                {platformLinks.map((item) => (
                  <a
                    key={item.label}
                    href={item.href}
                    onClick={closeAll}
                    className="flex flex-col px-3 py-2.5 rounded-xl hover:bg-neutral-50 transition-colors duration-150 group"
                  >
                    <span className="text-sm font-medium text-neutral-900 group-hover:text-blue-600 transition-colors duration-150">{item.label}</span>
                    <span className="text-xs text-neutral-400 mt-0.5 leading-relaxed">{item.desc}</span>
                  </a>
                ))}
              </div>
            )}
          </div>

          {/* Industries dropdown */}
          <div ref={industryRef} className="relative">
            <button
              onClick={() => { setIndustryOpen(!industryOpen); setPlatformOpen(false); setCompanyOpen(false); }}
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm font-medium text-neutral-600 hover:text-neutral-900 hover:bg-neutral-50 transition-colors duration-150"
            >
              Industries
              <ChevronDown size={13} strokeWidth={2} className={`transition-transform duration-200 ${industryOpen ? "rotate-180" : ""}`} />
            </button>
            {industryOpen && (
              <div
                className="absolute top-full left-1/2 -translate-x-1/2 mt-2 bg-white rounded-2xl border border-neutral-100 p-3"
                style={{ width: "300px", boxShadow: "0 8px 32px -4px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)" }}
              >
                {/* Live */}
                <p className="text-[10px] font-bold uppercase tracking-widest text-neutral-400 px-2 mb-1.5">Live</p>
                {industryLive.map((item) => (
                  <a
                    key={item.label}
                    href={item.href}
                    onClick={closeAll}
                    className="flex items-center justify-between px-2 py-2 rounded-lg hover:bg-neutral-50 transition-colors duration-150 mb-1"
                  >
                    <span className="text-sm font-medium text-neutral-900">{item.label}</span>
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                      style={{ backgroundColor: "rgba(16,185,129,0.1)", color: "#059669" }}>
                      Live
                    </span>
                  </a>
                ))}

                {/* Coming Soon */}
                <div className="mt-3 pt-3 border-t border-neutral-100">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-neutral-400 px-2 mb-1.5">Coming Soon</p>
                  <div className="grid grid-cols-2 gap-x-1">
                    {industryComingSoon.map((label) => (
                      <div key={label}
                        className="flex items-center justify-between px-2 py-1.5 rounded-lg"
                      >
                        <span className="text-sm font-medium text-neutral-400">{label}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Footer note */}
                <div className="mt-3 pt-3 border-t border-neutral-100 px-2">
                  <p className="text-[11px] text-neutral-400 leading-relaxed">
                    One platform. Configurable per industry.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Company dropdown */}
          <div ref={companyRef} className="relative">
            <button
              onClick={() => { setCompanyOpen(!companyOpen); setPlatformOpen(false); setIndustryOpen(false); }}
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm font-medium text-neutral-600 hover:text-neutral-900 hover:bg-neutral-50 transition-colors duration-150"
            >
              Company
              <ChevronDown size={13} strokeWidth={2} className={`transition-transform duration-200 ${companyOpen ? "rotate-180" : ""}`} />
            </button>
            {companyOpen && (
              <div
                className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-44 bg-white rounded-2xl shadow-xl border border-neutral-100 p-2"
                style={{ boxShadow: "0 8px 32px -4px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)" }}
              >
                {companyLinks.map((item) => (
                  <a
                    key={item.label}
                    href={item.href}
                    onClick={closeAll}
                    className="block px-3 py-2.5 rounded-xl text-sm font-medium text-neutral-900 hover:bg-neutral-50 transition-colors duration-150"
                  >
                    {item.label}
                  </a>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Desktop CTA */}
        <a
          href="/contact"
          className="hidden md:inline-flex items-center gap-2 shrink-0 text-sm font-semibold text-white transition-all duration-150 hover:opacity-90 active:scale-[0.98]"
          style={{
            padding: "0 22px",
            height: "40px",
            borderRadius: "999px",
            backgroundColor: "#2563EB",
            boxShadow: "0 1px 3px rgba(37,99,235,0.25)",
          }}
        >
          Request Demo
          <ArrowRight size={13} strokeWidth={2.2} />
        </a>

        {/* Mobile hamburger */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="md:hidden p-2 -mr-1 text-neutral-600 hover:text-neutral-900 transition-colors"
          aria-label="Menu"
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </nav>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="md:hidden bg-white border-t border-neutral-100">
          <div className="max-w-6xl mx-auto px-6 py-6 flex flex-col gap-1">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 mb-2 px-2">Platform</p>
            <a href="/platform" onClick={() => setMobileOpen(false)}
              className="text-sm font-semibold text-blue-600 py-2 px-2 rounded-lg hover:bg-blue-50 transition-colors">
              Platform Overview →
            </a>
            {platformLinks.map((item) => (
              <a key={item.label} href={item.href} onClick={() => setMobileOpen(false)}
                className="text-sm font-medium text-neutral-700 hover:text-neutral-900 transition-colors py-2 px-2 rounded-lg hover:bg-neutral-50">
                {item.label}
              </a>
            ))}
            <div className="h-px bg-neutral-100 my-3" />
            <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 mb-2 px-2">Industries</p>
            {industryLive.map((item) => (
              <a key={item.label} href={item.href} onClick={() => setMobileOpen(false)}
                className="flex items-center justify-between text-sm font-medium text-neutral-900 py-2 px-2 rounded-lg hover:bg-neutral-50 transition-colors">
                {item.label}
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                  style={{ backgroundColor: "rgba(16,185,129,0.1)", color: "#059669" }}>
                  Live
                </span>
              </a>
            ))}
            <div className="grid grid-cols-2 gap-x-1 mt-1">
              {industryComingSoon.map((label) => (
                <div key={label} className="flex items-center px-2 py-1.5">
                  <span className="text-sm font-medium text-neutral-400">{label}</span>
                </div>
              ))}
            </div>
            <p className="text-[11px] text-neutral-400 px-2 mt-1">One platform. Configurable per industry.</p>
            <div className="h-px bg-neutral-100 my-3" />
            {companyLinks.map((item) => (
              <a key={item.label} href={item.href} onClick={() => setMobileOpen(false)}
                className="text-sm font-medium text-neutral-700 hover:text-neutral-900 transition-colors py-2 px-2 rounded-lg hover:bg-neutral-50">
                {item.label}
              </a>
            ))}
            <a href="/contact" onClick={() => setMobileOpen(false)}
              className="mt-3 inline-flex items-center justify-center gap-2 text-sm font-semibold text-white rounded-full py-3"
              style={{ backgroundColor: "#2563EB" }}>
              Request Demo
              <ArrowRight size={14} strokeWidth={2.2} />
            </a>
          </div>
        </div>
      )}
    </header>
  );
}

function LogoMark() {
  return (
    <svg width="30" height="30" viewBox="0 0 32 32" fill="none">
      <rect width="32" height="32" rx="7" fill="#2563EB" />
      <rect x="7" y="9" width="18" height="4" rx="2" fill="white" />
      <rect x="7" y="15" width="13" height="4" rx="2" fill="white" opacity="0.6" />
      <rect x="7" y="21" width="8" height="4" rx="2" fill="white" opacity="0.3" />
    </svg>
  );
}
