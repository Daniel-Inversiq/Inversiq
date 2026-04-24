import { NextResponse } from "next/server";
import { buildBackendUrl, clearFrontendAuthCookie, getFrontendAccessTokenCookie } from "../_shared";

export async function POST(request: Request) {
  const token = getFrontendAccessTokenCookie(request);

  try {
    await fetch(buildBackendUrl("/auth/logout"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({}),
      cache: "no-store",
    });
  } catch {
    // Always clear local auth cookie, even if backend is unreachable.
  }

  const response = NextResponse.json({ ok: true });
  clearFrontendAuthCookie(response);
  return response;
}
