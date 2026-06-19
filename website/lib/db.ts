/**
 * lib/db.ts
 * Supabase database client — vervangt de eerdere better-sqlite3 implementatie.
 *
 * Alle functies zijn async omdat Supabase via HTTP werkt.
 *
 * VEILIGHEID:
 *   SUPABASE_SERVICE_ROLE_KEY wordt uitsluitend server-side gebruikt.
 *   Dit bestand mag nooit worden geïmporteerd vanuit een client component.
 *   De service role bypast Row Level Security — houd de key geheim.
 *
 * ─── DASHBOARD VOORBEREIDING ──────────────────────────────────────────────────
 * Alle scan-data is beschikbaar via:
 *   - insertScan(data)    — scan opslaan, geeft id terug
 *   - getScans(limit)     — alle scans, nieuwste eerst
 *   - getScanById(id)     — één scan op id
 *   - getScansCount()     — totaal aantal
 *
 * Gebruik deze helpers in app/api/admin/scans/route.ts of een toekomstig
 * dashboard onder app/admin/...
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const TABLE = "automation_scans";

/* ── Singleton ────────────────────────────────────────────── */
// Global singleton zodat Next.js dev hot-reload niet meerdere clients aanmaakt.
const globalWithSupa = global as typeof global & {
  _supabase?: SupabaseClient;
};

/**
 * Log een Supabase/fetch fout uitgebreid zonder secrets te lekken.
 * Logt: error.name/message/stack, cause.code/errno/syscall/hostname,
 * en de Supabase hostname voor DNS/netwerk diagnose.
 */
export function logDbError(label: string, err: unknown, supabaseUrl?: string): void {
  const e = err as Error & { cause?: NodeJS.ErrnoException & { hostname?: string } };

  console.error(`[db] ${label} — error.name:`, e?.name ?? "unknown");
  console.error(`[db] ${label} — error.message:`, e?.message ?? "unknown");

  if (e?.stack) {
    // Stack kan lang zijn; log de eerste 5 regels
    const stackLines = e.stack.split("\n").slice(0, 5).join("\n");
    console.error(`[db] ${label} — error.stack (top 5):`, stackLines);
  }

  if (e?.cause) {
    const c = e.cause;
    console.error(`[db] ${label} — cause.name:`,    c?.name    ?? "—");
    console.error(`[db] ${label} — cause.message:`, c?.message ?? "—");
    console.error(`[db] ${label} — cause.code:`,    c?.code    ?? "—");
    console.error(`[db] ${label} — cause.errno:`,   c?.errno   ?? "—");
    console.error(`[db] ${label} — cause.syscall:`, c?.syscall ?? "—");
    // hostname is veilig om te loggen (is de Supabase host, geen secret)
    if (c?.hostname) {
      console.error(`[db] ${label} — cause.hostname:`, c.hostname);
    }
  }

  // Log de Supabase hostname voor snelle DNS-check (geen key, geen path)
  if (supabaseUrl) {
    try {
      const host = new URL(supabaseUrl).hostname;
      console.error(`[db] ${label} — supabase hostname:`, host);
    } catch {
      console.error(`[db] ${label} — supabase URL kon niet worden geparsed`);
    }
  }
}

function getClient(): SupabaseClient {
  if (globalWithSupa._supabase) return globalWithSupa._supabase;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;

  console.log("[db] Supabase URL present:", !!url);
  console.log("[db] Service role key present:", !!key);

  if (!url || !key) {
    throw new Error(
      "Omgevingsvariabelen ontbreken: stel NEXT_PUBLIC_SUPABASE_URL en " +
        "SUPABASE_SERVICE_ROLE_KEY in via .env.local of Netlify."
    );
  }

  globalWithSupa._supabase = createClient(url, key, {
    auth: { persistSession: false },
  });

  return globalWithSupa._supabase;
}

/* ── Types ────────────────────────────────────────────────── */
export interface ScanRow {
  id: number;
  created_at: string;

  // Stap 1
  company_name: string;
  industry: string;
  employees: string;
  tools: string[];                    // jsonb array in Supabase

  // Stap 2
  pain_points: string[];              // jsonb array in Supabase
  custom_problem_description: string | null;

  // Stap 3
  hours_lost: string;
  urgency: string;

  // Stap 4
  timeline: string | null;
  name: string;
  email: string;
  phone: string | null;

  // Rapport
  score: number;
  generated_report: Record<string, unknown>;  // jsonb object in Supabase
}

export interface ScanInsert {
  company_name: string;
  industry: string;
  employees: string;
  tools: string[];
  pain_points: string[];
  custom_problem_description?: string;
  hours_lost: string;
  urgency: string;
  timeline?: string;
  name: string;
  email: string;
  phone?: string;
  score: number;
  generated_report: object;
}

/* ── Helpers ──────────────────────────────────────────────── */

/** Sla een voltooide scan op. Geeft het nieuwe id terug. */
export async function insertScan(data: ScanInsert): Promise<number> {
  const client = getClient();

  const { data: row, error } = await client
    .from(TABLE)
    .insert({
      company_name:               data.company_name,
      industry:                   data.industry,
      employees:                  data.employees,
      tools:                      data.tools,
      pain_points:                data.pain_points,
      custom_problem_description: data.custom_problem_description ?? null,
      hours_lost:                 data.hours_lost,
      urgency:                    data.urgency,
      timeline:                   data.timeline ?? null,
      name:                       data.name,
      email:                      data.email,
      phone:                      data.phone ?? null,
      score:                      data.score,
      generated_report:           data.generated_report,
    })
    .select("id")
    .single();

  if (error) {
    const wrapped = new Error(`[db] insertScan mislukt: ${error.message}`);
    logDbError("insertScan", wrapped, process.env.NEXT_PUBLIC_SUPABASE_URL);
    throw wrapped;
  }
  return (row as { id: number }).id;
}

/** Alle scans, nieuwste eerst. Optioneel beperkt tot `limit` rijen. */
export async function getScans(limit = 500): Promise<ScanRow[]> {
  const client = getClient();

  let data, error;
  try {
    ({ data, error } = await client
      .from(TABLE)
      .select("*")
      .order("created_at", { ascending: false })
      .limit(limit));
  } catch (fetchErr) {
    logDbError("getScans fetch", fetchErr, process.env.NEXT_PUBLIC_SUPABASE_URL);
    throw new Error(`[db] getScans mislukt: ${fetchErr instanceof Error ? fetchErr.message : "unknown"}`);
  }

  if (error) {
    const wrapped = new Error(`[db] getScans mislukt: ${error.message}`);
    logDbError("getScans", wrapped, process.env.NEXT_PUBLIC_SUPABASE_URL);
    throw wrapped;
  }
  return (data ?? []) as ScanRow[];
}

/** Één scan op id. */
export async function getScanById(id: number): Promise<ScanRow | undefined> {
  const client = getClient();

  let data, error;
  try {
    ({ data, error } = await client
      .from(TABLE)
      .select("*")
      .eq("id", id)
      .single());
  } catch (fetchErr) {
    logDbError("getScanById fetch", fetchErr, process.env.NEXT_PUBLIC_SUPABASE_URL);
    throw new Error(`[db] getScanById mislukt: ${fetchErr instanceof Error ? fetchErr.message : "unknown"}`);
  }

  if (error) {
    if (error.code === "PGRST116") return undefined;
    const wrapped = new Error(`[db] getScanById mislukt: ${error.message}`);
    logDbError("getScanById", wrapped, process.env.NEXT_PUBLIC_SUPABASE_URL);
    throw wrapped;
  }

  return data as ScanRow;
}

/** Totaal aantal opgeslagen scans. */
export async function getScansCount(): Promise<number> {
  const client = getClient();

  let count, error;
  try {
    ({ count, error } = await client
      .from(TABLE)
      .select("*", { count: "exact", head: true }));
  } catch (fetchErr) {
    logDbError("getScansCount fetch", fetchErr, process.env.NEXT_PUBLIC_SUPABASE_URL);
    throw new Error(`[db] getScansCount mislukt: ${fetchErr instanceof Error ? fetchErr.message : "unknown"}`);
  }

  if (error) {
    const wrapped = new Error(`[db] getScansCount mislukt: ${error.message}`);
    logDbError("getScansCount", wrapped, process.env.NEXT_PUBLIC_SUPABASE_URL);
    throw wrapped;
  }
  return count ?? 0;
}
