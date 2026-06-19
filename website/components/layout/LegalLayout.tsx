import React from "react";

interface LegalLayoutProps {
  badge: string;
  title: string;
  intro: string;
  lastUpdated: string;
  children: React.ReactNode;
}

export default function LegalLayout({
  badge,
  title,
  intro,
  lastUpdated,
  children,
}: LegalLayoutProps) {
  return (
    <div className="bg-white min-h-screen">
      <div className="max-w-[820px] mx-auto px-6 pt-32 pb-24">

        {/* Page header */}
        <div className="mb-14 pb-10" style={{ borderBottom: "1px solid #f0f0f0" }}>
          <div className="flex items-center gap-2 mb-5">
            <span
              className="inline-flex items-center px-3 py-1 rounded-full text-[11px] font-semibold uppercase tracking-widest"
              style={{
                backgroundColor: "rgba(37,99,235,0.07)",
                color: "#2563EB",
                border: "1px solid rgba(37,99,235,0.12)",
              }}
            >
              {badge}
            </span>
          </div>
          <h1 className="text-4xl lg:text-5xl font-bold tracking-tight text-neutral-900 mb-5">
            {title}
          </h1>
          <p className="text-lg text-neutral-500 leading-relaxed max-w-xl mb-6">
            {intro}
          </p>
          <p className="text-sm text-neutral-400">
            Laatst bijgewerkt: <span className="text-neutral-500">{lastUpdated}</span>
          </p>
        </div>

        {/* Body */}
        <div className="legal-content">
          {children}
        </div>

      </div>

      {/* Scoped prose styles */}
      <style>{`
        .legal-content ul {
          list-style: none;
          padding: 0;
          margin: 0;
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }
        .legal-content ul li {
          padding-left: 1.25rem;
          position: relative;
          color: #525252;
          font-size: 0.9375rem;
          line-height: 1.7;
        }
        .legal-content ul li::before {
          content: "–";
          position: absolute;
          left: 0;
          color: #a3a3a3;
        }
        .legal-content a {
          color: #2563EB;
          text-decoration: none;
        }
        .legal-content a:hover {
          text-decoration: underline;
        }
      `}</style>
    </div>
  );
}
