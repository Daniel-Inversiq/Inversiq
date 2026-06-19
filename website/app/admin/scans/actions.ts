"use server";

import { cookies } from "next/headers";
import { SESSION_COOKIE } from "@/lib/adminAuth";

/**
 * Server-side: controleert of de huidige request een geldige sessie-cookie heeft.
 * Login en logout lopen via /api/admin/login en /api/admin/logout (Route Handlers).
 */
export async function isAuthenticated(): Promise<boolean> {
  const secret = process.env.ADMIN_SECRET;
  if (!secret) return false;

  try {
    const cookieStore = await cookies();
    const session     = cookieStore.get(SESSION_COOKIE)?.value ?? "";
    return session === secret;
  } catch {
    return false;
  }
}
