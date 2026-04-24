import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { APP_ROUTES } from "@/lib/routes";

const AUTH_PAGES = new Set([APP_ROUTES.login, APP_ROUTES.register]);
const PROTECTED_PREFIXES = [
  "/app",
  "/dashboard",
  "/review",
  "/offertes",
  "/quotes",
  "/jobs",
  "/settings",
  "/agenda",
  "/workflows",
  "/customers",
  "/uploads",
  "/billing",
  "/handleiding",
];

function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasAccessToken = Boolean(request.cookies.get("access_token")?.value);
  const isAuthPage = AUTH_PAGES.has(pathname);

  if (isProtectedPath(pathname) && !hasAccessToken) {
    const loginUrl = new URL(APP_ROUTES.login, request.url);
    loginUrl.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(loginUrl);
  }

  if (isAuthPage && hasAccessToken) {
    return NextResponse.redirect(new URL(APP_ROUTES.dashboard, request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
