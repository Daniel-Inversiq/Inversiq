import type { Metadata } from "next";
import { getScans, getScansCount, type ScanRow } from "@/lib/db";
import { isAuthenticated } from "./actions";

export const metadata: Metadata = {
  title:  "Admin — AI-scan overzicht",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

/* ══════════════════════════════════════════════════════════
   Page
══════════════════════════════════════════════════════════ */
export default async function AdminScansPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const params = await searchParams;
  const authed = await isAuthenticated();

  if (!authed) {
    return <LoginScreen error={params.error} />;
  }

  // ── Supabase ophalen met error-handling ──────────────────
  // Vang alle DB-fouten op zodat een Supabase timeout de pagina
  // niet crasht met een "server-side application error".
  let scans: ScanRow[]  = [];
  let total             = 0;
  let dbError: string | null = null;

  try {
    console.log("[admin/scans] Ophalen scans uit Supabase…");
    const t0 = Date.now();

    [scans, total] = await Promise.all([getScans(500), getScansCount()]);

    console.log(`[admin/scans] ${total} scans opgehaald in ${Date.now() - t0}ms`);
  } catch (err) {
    // Log de fout zonder secrets te tonen
    const msg = err instanceof Error ? err.message : "Onbekende fout";
    console.error("[admin/scans] DB-fout:", msg);
    dbError = msg;
  }

  return <Dashboard scans={scans} total={total} dbError={dbError} />;
}

/* ══════════════════════════════════════════════════════════
   LoginScreen
   – form POSTt naar /api/admin/login (Route Handler)
   – betrouwbaarder dan server actions + redirect op Netlify
══════════════════════════════════════════════════════════ */
function LoginScreen({ error }: { error?: string }) {
  const configured = !!process.env.ADMIN_SECRET;

  return (
    <div
      className="min-h-screen flex items-center justify-center px-6"
      style={{ backgroundColor: "#f8fafc" }}
    >
      <div
        className="w-full max-w-sm rounded-2xl p-8 bg-white"
        style={{
          border:    "1px solid rgba(0,0,0,0.08)",
          boxShadow: "0 4px 24px rgba(0,0,0,0.06)",
        }}
      >
        {/* Logo row */}
        <div className="flex items-center gap-2.5 mb-8">
          <LogoMark />
          <span className="font-semibold tracking-tight text-[1.0625rem] text-neutral-900">
            Invers<span style={{ color: "#2563EB" }}>iq</span>
          </span>
          <span
            className="ml-auto text-[10px] font-semibold uppercase tracking-widest px-2.5 py-1 rounded-full"
            style={{
              backgroundColor: "rgba(37,99,235,0.07)",
              color:           "#2563EB",
              border:          "1px solid rgba(37,99,235,0.15)",
            }}
          >
            Admin
          </span>
        </div>

        <h1 className="text-xl font-bold text-neutral-900 mb-1.5 tracking-tight">
          Inloggen
        </h1>
        <p className="text-sm text-neutral-500 mb-6 leading-relaxed">
          Voer het admin-wachtwoord in om het scan-overzicht te bekijken.
        </p>

        {!configured && (
          <Alert variant="error" className="mb-5">
            <strong>ADMIN_SECRET is niet geconfigureerd.</strong>
            <br />
            Voeg{" "}
            <code className="text-xs bg-red-50 px-1 py-0.5 rounded font-mono">
              ADMIN_SECRET=…
            </code>{" "}
            toe aan{" "}
            <code className="text-xs bg-red-50 px-1 py-0.5 rounded font-mono">
              .env.local
            </code>{" "}
            en herstart de server.
          </Alert>
        )}

        {error === "wrong_password" && (
          <Alert variant="error" className="mb-5">
            Onjuist wachtwoord. Probeer het opnieuw.
          </Alert>
        )}

        {error === "not_configured" && (
          <Alert variant="error" className="mb-5">
            ADMIN_SECRET is niet ingesteld op de server.
          </Alert>
        )}

        {/* action="/api/admin/login" — Route Handler, geen server action */}
        <form method="POST" action="/api/admin/login" className="flex flex-col gap-3">
          <input
            type="password"
            name="password"
            placeholder="Wachtwoord"
            required
            autoFocus
            disabled={!configured}
            className="w-full px-4 py-2.5 rounded-xl text-sm text-neutral-800 bg-neutral-50 outline-none border border-neutral-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all duration-200 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!configured}
            className="w-full py-3 rounded-full text-sm font-semibold text-white transition-opacity duration-150 hover:opacity-90 active:scale-[0.98] disabled:opacity-40"
            style={{ backgroundColor: "#2563EB" }}
          >
            Inloggen
          </button>
        </form>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   Dashboard
══════════════════════════════════════════════════════════ */
function Dashboard({
  scans,
  total,
  dbError,
}: {
  scans: ScanRow[];
  total: number;
  dbError: string | null;
}) {
  return (
    <div className="min-h-screen" style={{ backgroundColor: "#f8fafc" }}>

      {/* ── Top bar ─────────────────────────────────────────── */}
      <div
        className="sticky top-0 z-10 bg-white"
        style={{ borderBottom: "1px solid rgba(0,0,0,0.07)" }}
      >
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <LogoMark size={22} />
            <span className="font-semibold tracking-tight text-[1rem] text-neutral-900">
              Invers<span style={{ color: "#2563EB" }}>iq</span>
            </span>
            <span className="text-neutral-200 select-none">·</span>
            <span
              className="text-[10px] font-semibold uppercase tracking-widest px-2 py-0.5 rounded-full"
              style={{
                backgroundColor: "rgba(37,99,235,0.07)",
                color:           "#2563EB",
                border:          "1px solid rgba(37,99,235,0.15)",
              }}
            >
              Admin
            </span>
          </div>

          {/* action="/api/admin/logout" — Route Handler */}
          <form method="POST" action="/api/admin/logout">
            <button
              type="submit"
              className="text-xs font-medium text-neutral-400 hover:text-neutral-700 transition-colors duration-150 px-3 py-1.5 rounded-lg hover:bg-neutral-100"
            >
              Uitloggen
            </button>
          </form>
        </div>
      </div>

      {/* ── Page header ─────────────────────────────────────── */}
      <div className="bg-white" style={{ borderBottom: "1px solid rgba(0,0,0,0.06)" }}>
        <div className="max-w-6xl mx-auto px-6 py-8">
          <h1 className="text-2xl font-bold tracking-tight text-neutral-900 mb-1">
            AI-scan overzicht
          </h1>
          <p className="text-sm text-neutral-500">
            Bekijk welke bedrijven de automatiseringsscan hebben ingevuld.
          </p>
        </div>
      </div>

      {/* ── Content ─────────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col gap-6">

        {/* DB-fout banner — vervangt crash */}
        {dbError && (
          <Alert variant="error">
            <strong>Database niet bereikbaar.</strong>
            <br />
            <span className="text-xs opacity-80">
              Controleer de Supabase verbinding en omgevingsvariabelen. Ververs de pagina om het opnieuw te proberen.
            </span>
          </Alert>
        )}

        {/* Stat cards */}
        {!dbError && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatCard label="Totaal scans"  value={String(total)} />
            <StatCard label="Gem. score"    value={avgScore(scans)} />
            <StatCard label="Hoge urgentie" value={countUrgency(scans, ["Hoog", "Zeer hoog"])} />
            <StatCard label="Deze maand"    value={countThisMonth(scans)} />
          </div>
        )}

        {/* Table */}
        {!dbError && (
          scans.length === 0 ? (
            <EmptyState />
          ) : (
            <div
              className="rounded-2xl bg-white overflow-hidden"
              style={{
                border:    "1px solid rgba(0,0,0,0.08)",
                boxShadow: "0 1px 6px rgba(0,0,0,0.04)",
              }}
            >
              {/* Table header bar */}
              <div
                className="px-6 py-4 flex items-center justify-between"
                style={{ borderBottom: "1px solid rgba(0,0,0,0.06)" }}
              >
                <p className="text-sm font-semibold text-neutral-900">Ingevulde scans</p>
                <span className="text-xs text-neutral-400 tabular-nums">
                  {total} {total === 1 ? "resultaat" : "resultaten"}
                </span>
              </div>

              {/* Scrollable table */}
              <div className="overflow-x-auto">
                <table className="w-full text-sm min-w-[720px]">
                  <thead>
                    <tr style={{ backgroundColor: "#fafafa", borderBottom: "1px solid rgba(0,0,0,0.07)" }}>
                      {[
                        { label: "Datum",          w: "w-36" },
                        { label: "Bedrijf",        w: "w-40" },
                        { label: "Contactpersoon", w: "w-36" },
                        { label: "E-mail",         w: "" },
                        { label: "Branche",        w: "w-40" },
                        { label: "Score",          w: "w-24" },
                        { label: "Urgentie",       w: "w-28" },
                      ].map(({ label, w }) => (
                        <th
                          key={label}
                          className={`px-5 py-3 text-left text-[10px] font-semibold uppercase tracking-widest text-neutral-400 whitespace-nowrap ${w}`}
                        >
                          {label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {scans.map((scan, i) => (
                      <TableRow key={scan.id} scan={scan} last={i === scans.length - 1} />
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )
        )}

      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   TableRow
══════════════════════════════════════════════════════════ */
function TableRow({ scan, last }: { scan: ScanRow; last: boolean }) {
  const scoreColor =
    scan.score >= 65 ? "#2563EB"
    : scan.score >= 40 ? "#0284c7"
    : "#64748b";

  return (
    <tr
      className="hover:bg-neutral-50 transition-colors duration-100"
      style={last ? {} : { borderBottom: "1px solid rgba(0,0,0,0.05)" }}
    >
      <td className="px-5 py-4 whitespace-nowrap text-[13px] text-neutral-400 tabular-nums">
        {formatDate(scan.created_at)}
      </td>
      <td className="px-5 py-4 whitespace-nowrap">
        <span className="text-[13px] font-semibold text-neutral-900">{scan.company_name}</span>
      </td>
      <td className="px-5 py-4 whitespace-nowrap text-[13px] text-neutral-600">
        {scan.name}
      </td>
      <td className="px-5 py-4 whitespace-nowrap">
        <a
          href={`mailto:${scan.email}`}
          className="text-[13px] font-medium transition-opacity duration-150 hover:opacity-70"
          style={{ color: "#2563EB" }}
        >
          {scan.email}
        </a>
      </td>
      <td className="px-5 py-4 whitespace-nowrap text-[13px] text-neutral-500">
        {scan.industry}
      </td>
      <td className="px-5 py-4 whitespace-nowrap">
        <span
          className="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-semibold tabular-nums"
          style={{
            backgroundColor: `${scoreColor}12`,
            color:            scoreColor,
            border:           `1px solid ${scoreColor}25`,
          }}
        >
          {scan.score} / 100
        </span>
      </td>
      <td className="px-5 py-4 whitespace-nowrap">
        <UrgencyBadge urgency={scan.urgency} />
      </td>
    </tr>
  );
}

/* ══════════════════════════════════════════════════════════
   StatCard
══════════════════════════════════════════════════════════ */
function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="rounded-xl p-5 bg-white flex flex-col"
      style={{
        border:    "1px solid rgba(0,0,0,0.08)",
        boxShadow: "0 1px 3px rgba(0,0,0,0.03)",
      }}
    >
      <div
        style={{
          width: "24px", height: "2px", borderRadius: "999px",
          backgroundColor: "rgba(37,99,235,0.45)",
          marginBottom: "12px", flexShrink: 0,
        }}
      />
      <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 mb-2">
        {label}
      </p>
      <p
        className="text-3xl font-bold tracking-tight tabular-nums"
        style={{ color: "#0a0a0a", letterSpacing: "-0.04em" }}
      >
        {value}
      </p>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   UrgencyBadge
══════════════════════════════════════════════════════════ */
function UrgencyBadge({ urgency }: { urgency: string }) {
  const styles: Record<string, { bg: string; color: string; border: string }> = {
    "Zeer hoog": { bg: "rgba(239,68,68,0.07)",  color: "#dc2626", border: "rgba(239,68,68,0.18)"  },
    "Hoog":      { bg: "rgba(249,115,22,0.07)", color: "#ea580c", border: "rgba(249,115,22,0.18)" },
    "Gemiddeld": { bg: "rgba(234,179,8,0.07)",  color: "#b45309", border: "rgba(234,179,8,0.2)"   },
    "Laag":      { bg: "rgba(0,0,0,0.04)",      color: "#737373", border: "rgba(0,0,0,0.09)"      },
  };
  const s = styles[urgency] ?? styles["Laag"];
  return (
    <span
      className="inline-flex px-2.5 py-1 rounded-full text-[11px] font-semibold whitespace-nowrap"
      style={{ backgroundColor: s.bg, color: s.color, border: `1px solid ${s.border}` }}
    >
      {urgency}
    </span>
  );
}

/* ══════════════════════════════════════════════════════════
   EmptyState
══════════════════════════════════════════════════════════ */
function EmptyState() {
  return (
    <div
      className="rounded-2xl py-20 px-6 bg-white text-center"
      style={{ border: "1px solid rgba(0,0,0,0.08)", boxShadow: "0 1px 6px rgba(0,0,0,0.04)" }}
    >
      <div
        className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto mb-4"
        style={{ backgroundColor: "rgba(37,99,235,0.07)", border: "1px solid rgba(37,99,235,0.12)" }}
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <rect x="3" y="5" width="14" height="11" rx="2" stroke="#2563EB" strokeWidth="1.5" />
          <path d="M7 9h6M7 12h4" stroke="#2563EB" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </div>
      <p className="text-sm font-semibold text-neutral-700 mb-1">Nog geen scans ingevuld.</p>
      <p className="text-xs text-neutral-400 leading-relaxed max-w-xs mx-auto">
        Nieuwe scans verschijnen hier zodra bezoekers de AI-automatisering scan voltooien.
      </p>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   Alert
══════════════════════════════════════════════════════════ */
function Alert({
  variant,
  className = "",
  children,
}: {
  variant: "error";
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`rounded-xl px-4 py-3 text-sm leading-relaxed ${className}`}
      style={{
        backgroundColor: "rgba(239,68,68,0.06)",
        border:          "1px solid rgba(239,68,68,0.18)",
        color:           "#dc2626",
      }}
    >
      {children}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   LogoMark
══════════════════════════════════════════════════════════ */
function LogoMark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 30 30" fill="none" className="flex-shrink-0">
      <rect width="30" height="30" rx="8" fill="#0a0a0a" />
      <path d="M9 15h4.5m3 0H21M15 9v4.5m0 3V21" stroke="white" strokeWidth="2" strokeLinecap="round" />
      <circle cx="15" cy="15" r="2.5" fill="white" />
    </svg>
  );
}

/* ══════════════════════════════════════════════════════════
   Helpers
══════════════════════════════════════════════════════════ */
function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat("nl-NL", {
      day: "numeric", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
      timeZone: "Europe/Amsterdam",
    }).format(new Date(iso));
  } catch { return iso; }
}

function avgScore(scans: ScanRow[]): string {
  if (!scans.length) return "—";
  return `${Math.round(scans.reduce((s, r) => s + r.score, 0) / scans.length)}`;
}

function countUrgency(scans: ScanRow[], levels: string[]): string {
  return String(scans.filter((s) => levels.includes(s.urgency)).length);
}

function countThisMonth(scans: ScanRow[]): string {
  const now = new Date();
  return String(scans.filter((s) => {
    const d = new Date(s.created_at);
    return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
  }).length);
}
