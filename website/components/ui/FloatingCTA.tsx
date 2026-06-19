"use client";

import { useEffect, useState } from "react";
import { X, ArrowRight, Zap } from "lucide-react";

const STORAGE_KEY = "inversiq_floating_cta_dismissed";
const DISMISS_DAYS = 7;
const SHOW_AFTER_MS = 20_000;
const SHOW_AFTER_SCROLL_PCT = 0.5;

export default function FloatingCTA() {
  const [visible, setVisible]   = useState(false);
  const [mounted, setMounted]   = useState(false);
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw && Date.now() < Number(raw)) return;
    setDismissed(false);
  }, []);

  useEffect(() => {
    if (dismissed) return;
    let triggered = false;

    function show() {
      if (triggered) return;
      triggered = true;
      setMounted(true);
      requestAnimationFrame(() => requestAnimationFrame(() => setVisible(true)));
    }

    const timer = setTimeout(show, SHOW_AFTER_MS);

    function onScroll() {
      const scrolled = window.scrollY / (document.body.scrollHeight - window.innerHeight);
      if (scrolled >= SHOW_AFTER_SCROLL_PCT) show();
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => { clearTimeout(timer); window.removeEventListener("scroll", onScroll); };
  }, [dismissed]);

  function dismiss() {
    setVisible(false);
    setTimeout(() => setMounted(false), 400);
    localStorage.setItem(STORAGE_KEY, String(Date.now() + DISMISS_DAYS * 86400000));
    setDismissed(true);
  }

  if (!mounted) return null;

  return (
    <div role="dialog" aria-label="Request a demo"
      style={{
        position: "fixed", bottom: "24px", right: "24px", zIndex: 50,
        width: "100%", maxWidth: "320px",
        backgroundColor: "#ffffff", borderRadius: "18px",
        border: "1px solid rgba(0,0,0,0.08)",
        boxShadow: "0 8px 32px -4px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)",
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0px)" : "translateY(12px)",
        transition: "opacity 380ms cubic-bezier(0.4,0,0.2,1), transform 380ms cubic-bezier(0.4,0,0.2,1)",
      }}>

      <button onClick={dismiss} aria-label="Dismiss"
        style={{ position: "absolute", top: "12px", right: "12px", width: "24px", height: "24px",
          display: "flex", alignItems: "center", justifyContent: "center",
          borderRadius: "6px", border: "none", backgroundColor: "transparent", cursor: "pointer", color: "#a3a3a3" }}
        onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = "rgba(0,0,0,0.05)"; (e.currentTarget as HTMLButtonElement).style.color = "#525252"; }}
        onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = "transparent"; (e.currentTarget as HTMLButtonElement).style.color = "#a3a3a3"; }}>
        <X size={13} strokeWidth={2.2} />
      </button>

      <div style={{ padding: "20px 20px 18px" }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: "12px", marginBottom: "10px" }}>
          <div style={{ flexShrink: 0, width: "36px", height: "36px", borderRadius: "10px",
            backgroundColor: "rgba(37,99,235,0.08)", border: "1px solid rgba(37,99,235,0.15)",
            display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Zap size={16} strokeWidth={1.75} style={{ color: "#2563EB" }} />
          </div>
          <p style={{ fontSize: "14px", fontWeight: 600, color: "#0a0a0a", lineHeight: "1.3",
            letterSpacing: "-0.01em", paddingTop: "2px", paddingRight: "20px" }}>
            See Inversiq on your processes
          </p>
        </div>

        <p style={{ fontSize: "13px", color: "#737373", lineHeight: "1.55", marginBottom: "16px" }}>
          A custom demo on your document types and workflows. Not a generic walkthrough.
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <a href="/contact"
            style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "6px",
              padding: "10px 16px", borderRadius: "10px", backgroundColor: "#2563EB", color: "white",
              fontSize: "13.5px", fontWeight: 600, textDecoration: "none" }}
            onMouseEnter={e => (e.currentTarget as HTMLAnchorElement).style.opacity = "0.9"}
            onMouseLeave={e => (e.currentTarget as HTMLAnchorElement).style.opacity = "1"}
            onMouseDown={e => (e.currentTarget as HTMLAnchorElement).style.transform = "scale(0.98)"}
            onMouseUp={e => (e.currentTarget as HTMLAnchorElement).style.transform = "scale(1)"}>
            Request a Demo
            <ArrowRight size={13} strokeWidth={2.2} />
          </a>
          <button onClick={dismiss}
            style={{ display: "flex", alignItems: "center", justifyContent: "center",
              padding: "8px 16px", borderRadius: "10px", backgroundColor: "transparent",
              color: "#a3a3a3", fontSize: "13px", fontWeight: 500, border: "none", cursor: "pointer" }}
            onMouseEnter={e => (e.currentTarget as HTMLButtonElement).style.color = "#525252"}
            onMouseLeave={e => (e.currentTarget as HTMLButtonElement).style.color = "#a3a3a3"}>
            Not now
          </button>
        </div>
      </div>
    </div>
  );
}
