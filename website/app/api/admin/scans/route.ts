/**
 * GET /api/admin/scans
 * Geeft alle opgeslagen AI-scan resultaten terug als JSON.
 *
 * ─── AUTHENTICATIE ────────────────────────────────────────────────────────────
 * Beveiligd via de ADMIN_SECRET environment variable.
 * Stuur mee als header: Authorization: Bearer <ADMIN_SECRET>
 *
 * TODO: Vervang dit door een volwaardige auth-oplossing (bijv. NextAuth of
 *       Clerk) zodra het dashboard verder wordt uitgebouwd.
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * Query parameters:
 *   ?limit=100     — max aantal rijen (default 100, max 1000)
 *   ?id=42         — één scan opvragen op id
 *
 * Gebruik:
 *   curl -H "Authorization: Bearer <ADMIN_SECRET>" https://inversiq.com/api/admin/scans
 */

import { NextRequest, NextResponse } from "next/server";
import { getScans, getScansCount, getScanById } from "@/lib/db";

const ADMIN_SECRET = process.env.ADMIN_SECRET;

function unauthorized() {
  return NextResponse.json({ error: "Niet geautoriseerd." }, { status: 401 });
}

function checkAuth(req: NextRequest): boolean {
  if (!ADMIN_SECRET) {
    console.warn("[admin] ADMIN_SECRET is niet ingesteld — endpoint is onbeveiligd!");
    return true;
  }
  const auth = req.headers.get("authorization") ?? "";
  return auth === `Bearer ${ADMIN_SECRET}`;
}

export async function GET(req: NextRequest) {
  if (!checkAuth(req)) return unauthorized();

  const url   = new URL(req.url);
  const limit = Math.min(Number(url.searchParams.get("limit") ?? "100"), 1000);
  const id    = url.searchParams.get("id");

  if (id) {
    const scan = await getScanById(Number(id));
    if (!scan) return NextResponse.json({ error: "Niet gevonden." }, { status: 404 });
    return NextResponse.json({ scan });
  }

  const [scans, count] = await Promise.all([getScans(limit), getScansCount()]);

  return NextResponse.json({ total: count, limit, scans });
}
