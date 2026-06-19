import { Mail, MapPin, Clock } from "lucide-react";

const platform = [
  { label: "Document Intelligence", href: "/#platform" },
  { label: "Computer Vision",       href: "/#platform" },
  { label: "Workflow Orchestration", href: "/#platform" },
  { label: "Decision Engine",       href: "/#platform" },
  { label: "AI Agents",             href: "/#platform" },
  { label: "Observability",         href: "/#platform" },
];

const industries = [
  { label: "Construction", tag: "Live",         href: "/#industries" },
  { label: "Insurance",    tag: "Coming Soon",  href: "/#industries" },
  { label: "Logistics",    tag: "Coming Soon",  href: "/#industries" },
  { label: "Field Services", tag: "Coming Soon", href: "/#industries" },
];

const company = [
  { label: "About",    href: "/#about" },
  { label: "Careers",  href: "/#careers" },
  { label: "Contact",  href: "/contact" },
];

export default function Footer() {
  return (
    <footer className="bg-white border-t border-neutral-100">
      <div className="max-w-6xl mx-auto px-6 pt-16 pb-8">

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-10 lg:gap-8 mb-14">

          {/* Brand */}
          <div className="sm:col-span-2 lg:col-span-2">
            <a href="/" className="inline-flex items-center gap-2.5 mb-5">
              <LogoMark />
              <span className="font-semibold text-neutral-900 tracking-tight text-[1.0625rem]">
                Invers<span style={{ color: "#2563EB" }}>iq</span>
              </span>
            </a>
            <p className="text-[11px] font-semibold uppercase tracking-widest mb-3" style={{ color: "#2563EB" }}>
              AI Decision Infrastructure · Inversiq
            </p>
            <p className="text-sm text-neutral-500 leading-relaxed max-w-[280px]">
              Inversiq is the AI decision infrastructure platform that reads documents, applies business logic,
              and executes workflows — across the operational industries that run the world.
            </p>
          </div>

          {/* Platform */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-5">Platform</p>
            <ul className="flex flex-col gap-3">
              {platform.map((link) => (
                <li key={link.label}>
                  <a href={link.href} className="text-sm text-neutral-500 hover:text-neutral-900 transition-colors duration-150">
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Industries */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-5">Industries</p>
            <ul className="flex flex-col gap-3">
              {industries.map((link) => (
                <li key={link.label} className="flex items-center gap-2">
                  <a href={link.href} className="text-sm text-neutral-500 hover:text-neutral-900 transition-colors duration-150">
                    {link.label}
                  </a>
                  {link.tag === "Live" && (
                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full"
                      style={{ backgroundColor: "rgba(16,185,129,0.10)", color: "#059669" }}>
                      Live
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>

          {/* Company + Contact */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-5">Company</p>
            <ul className="flex flex-col gap-3 mb-6">
              {company.map((link) => (
                <li key={link.label}>
                  <a href={link.href} className="text-sm text-neutral-500 hover:text-neutral-900 transition-colors duration-150">
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>

            <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-4">Contact</p>
            <ul className="flex flex-col gap-2.5">
              <li>
                <a href="mailto:info@inversiq.com"
                  className="inline-flex items-center gap-2 text-sm text-neutral-500 hover:text-neutral-900 transition-colors duration-150">
                  <Mail size={13} strokeWidth={1.75} className="shrink-0" style={{ color: "#2563EB" }} />
                  info@inversiq.com
                </a>
              </li>
              <li className="flex items-center gap-2 text-sm text-neutral-500">
                <MapPin size={13} strokeWidth={1.75} className="shrink-0" style={{ color: "#2563EB" }} />
                Amsterdam, Netherlands
              </li>
              <li className="text-sm text-neutral-400">KvK: 42027564</li>
            </ul>
          </div>
        </div>

        {/* Compliance strip */}
        <div className="flex flex-wrap items-center gap-3 mb-8 pb-8"
          style={{ borderBottom: "1px solid rgba(0,0,0,0.06)" }}>
          {["SOC 2 Type II", "GDPR Compliant", "EU AI Act Ready", "EU Hosted"].map((badge) => (
            <span key={badge} className="text-[11px] font-medium px-3 py-1.5 rounded-full"
              style={{ backgroundColor: "rgba(37,99,235,0.05)", color: "#64748B", border: "1px solid rgba(37,99,235,0.10)" }}>
              {badge}
            </span>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-neutral-400 order-2 sm:order-1">
            © {new Date().getFullYear()} Inversiq B.V. All rights reserved.
          </p>
          <div className="flex items-center gap-6 order-1 sm:order-2">
            <a href="/privacy" className="text-xs text-neutral-400 hover:text-neutral-700 transition-colors duration-150">
              Privacy Policy
            </a>
            <a href="/algemene-voorwaarden" className="text-xs text-neutral-400 hover:text-neutral-700 transition-colors duration-150">
              Terms of Service
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}

function LogoMark() {
  return (
    <svg width="28" height="28" viewBox="0 0 30 30" fill="none">
      <rect width="30" height="30" rx="8" fill="#0a0a0a" />
      <path d="M9 15h4.5m3 0H21M15 9v4.5m0 3V21" stroke="white" strokeWidth="2" strokeLinecap="round" />
      <circle cx="15" cy="15" r="2.5" fill="white" />
    </svg>
  );
}
