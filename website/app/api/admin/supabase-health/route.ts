/**
 * GET /api/admin/supabase-health
 *
 * Diagnostische endpoint — controleert of Supabase bereikbaar is vanuit
 * de Netlify serverless omgeving.
 *
 * Beveiligd met Authorization: Bearer <ADMIN_SECRET>.
 * Retourneert JSON zonder secrets.
 */

import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

export const dynamic = "force-dynamic";

interface HealthResult {
  envPresent: { url: boolean; key: boolean };
  supabaseHost: string | null;
  ok: boolean;
  durationMs: number | null;
  error: {
    name?: string;
    message?: string;
    stack?: string;
    cause?: {
      name?: string;
      message?: string;
      code?: string;
      errno?: number | string;
      syscall?: string;
      hostname?: string;
    };
  } | null;
}

export async function GET(req: NextRequest): Promise<NextResponse> {
  // ── Auth ────────────────────────────────────────────────
  const secret = process.env.ADMIN_SECRET;
  const auth   = req.headers.get("authorization") ?? "";
  const token  = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";

  if (!secret || token !== secret) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // ── Env check ───────────────────────────────────────────
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY ?? "";

  const result: HealthResult = {
    envPresent:  { url: !!url, key: !!key },
    supabaseHost: url ? (() => { try { return new URL(url).hostname; } catch { return null; } })() : null,
    ok:          false,
    durationMs:  null,
    error:       null,
  };

  if (!url || !key) {
    return NextResponse.json(result, { status: 200 });
  }

  // ── Supabase probe ──────────────────────────────────────
  // Minimale query: één rij ophalen — genoeg om network + auth te testen.
  const client = createClient(url, key, { auth: { persistSession: false } });
  const t0 = Date.now();

  try {
    const { error: qErr } = await client
      .from("automation_scans")
      .select("id")
      .limit(1);

    result.durationMs = Date.now() - t0;

    if (qErr) {
      result.ok    = false;
      result.error = { name: "SupabaseError", message: qErr.message };
    } else {
      result.ok = true;
    }
  } catch (err) {
    result.durationMs = Date.now() - t0;

    const e = err as Error & {
      cause?: NodeJS.ErrnoException & { hostname?: string };
    };

    result.error = {
      name:    e?.name,
      message: e?.message,
      // Stack: max 5 regels, geen absolute paths (kunnen build-paden bevatten)
      stack: e?.stack
        ? e.stack.split("\n").slice(0, 5).join(" | ")
        : undefined,
      cause: e?.cause
        ? {
            name:     e.cause.name,
            message:  e.cause.message,
            code:     e.cause.code,
            errno:    e.cause.errno,
            syscall:  e.cause.syscall,
            hostname: e.cause.hostname, // veilig: is Supabase host, geen secret
          }
        : undefined,
    };
  }

  console.log("[supabase-health]", JSON.stringify({
    ...result,
    // Nogmaals zeker: key nooit in log
    envPresent: result.envPresent,
  }));

  return NextResponse.json(result, { status: 200 });
}
