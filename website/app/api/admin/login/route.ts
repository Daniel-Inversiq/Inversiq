/**
 * POST /api/admin/login
 *
 * Vervangt de eerdere server action loginAction().
 * Route handlers zetten Set-Cookie direct op de HTTP response — betrouwbaarder
 * dan server actions + redirect() op Netlify serverless.
 */

import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE, COOKIE_MAX_AGE } from "@/lib/adminAuth";

export async function POST(req: NextRequest) {
  const secret = process.env.ADMIN_SECRET;

  if (!secret) {
    console.error("[admin/login] ADMIN_SECRET is niet geconfigureerd");
    return NextResponse.redirect(
      new URL("/admin/scans?error=not_configured", req.url)
    );
  }

  let password = "";
  try {
    const form = await req.formData();
    password = form.get("password")?.toString().trim() ?? "";
  } catch {
    return NextResponse.redirect(
      new URL("/admin/scans?error=wrong_password", req.url)
    );
  }

  if (password !== secret) {
    console.warn("[admin/login] Mislukte inlogpoging");
    return NextResponse.redirect(
      new URL("/admin/scans?error=wrong_password", req.url)
    );
  }

  console.log("[admin/login] Succesvol ingelogd");

  // Zet cookie direct op de redirect-response — geen server action overhead
  const response = NextResponse.redirect(new URL("/admin/scans", req.url));
  response.cookies.set(SESSION_COOKIE, secret, {
    httpOnly: true,
    secure:   process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge:   COOKIE_MAX_AGE,
    path:     "/",
  });

  return response;
}
