import { NextResponse } from "next/server";

export const ACCESS_TOKEN_COOKIE = "access_token";
const ONE_DAY_SECONDS = 60 * 60 * 24;

function getBackendBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";
}

export function buildBackendUrl(path: string): string {
  const baseUrl = getBackendBaseUrl();
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (!baseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured");
  }
  return `${baseUrl}${normalizedPath}`;
}

export function parseAccessTokenFromSetCookie(setCookieHeader: string | null): string | null {
  if (!setCookieHeader) {
    return null;
  }
  const tokenMatch = setCookieHeader.match(/(?:^|,\s*)access_token=([^;,\s]+)/i);
  if (!tokenMatch?.[1]) {
    return null;
  }
  return decodeURIComponent(tokenMatch[1]);
}

export function setFrontendAuthCookie(response: NextResponse, token: string): void {
  response.cookies.set({
    name: ACCESS_TOKEN_COOKIE,
    value: token,
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: ONE_DAY_SECONDS,
  });
}

export function clearFrontendAuthCookie(response: NextResponse): void {
  response.cookies.set({
    name: ACCESS_TOKEN_COOKIE,
    value: "",
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
}

export function getFrontendAccessTokenCookie(request: Request): string | null {
  const cookieHeader = request.headers.get("cookie") ?? "";
  const tokenMatch = cookieHeader.match(/(?:^|;\s*)access_token=([^;]+)/i);
  return tokenMatch?.[1] ? decodeURIComponent(tokenMatch[1]) : null;
}
