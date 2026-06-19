/**
 * POST /api/admin/logout
 *
 * Wist de sessie-cookie en stuurt terug naar het loginscherm.
 */

import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/adminAuth";

export async function POST(req: NextRequest) {
  const response = NextResponse.redirect(new URL("/admin/scans", req.url));
  response.cookies.set(SESSION_COOKIE, "", {
    httpOnly: true,
    secure:   process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge:   0,   // Direct verlopen
    path:     "/",
  });
  return response;
}
