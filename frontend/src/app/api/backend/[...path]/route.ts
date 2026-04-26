import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { ACCESS_TOKEN_COOKIE, buildBackendUrl } from "@/app/api/auth/_shared";

export const dynamic = "force-dynamic";

function joinBackendPath(segments: string[], search: string): string | null {
  if (!segments.length) {
    return null;
  }
  for (const segment of segments) {
    if (segment === ".." || segment === "." || segment.includes("\0")) {
      return null;
    }
  }
  return `/${segments.join("/")}${search}`;
}

async function proxyRequest(
  request: NextRequest,
  paramsPromise: Promise<{ path?: string[] }>,
): Promise<Response> {
  const { path: segments } = await paramsPromise;
  const joined = joinBackendPath(segments ?? [], request.nextUrl.search);
  if (!joined) {
    return NextResponse.json({ detail: "Invalid path" }, { status: 400 });
  }

  let targetUrl: string;
  try {
    targetUrl = buildBackendUrl(joined);
  } catch {
    return NextResponse.json({ detail: "Backend URL not configured" }, { status: 500 });
  }

  const cookieStore = await cookies();
  const token = cookieStore.get(ACCESS_TOKEN_COOKIE)?.value ?? null;

  const method = request.method.toUpperCase();
  const upstreamHeaders = new Headers();

  const contentType = request.headers.get("content-type");
  if (contentType) {
    upstreamHeaders.set("content-type", contentType);
  }

  const accept = request.headers.get("accept");
  upstreamHeaders.set("accept", accept ?? "application/json");

  if (token) {
    upstreamHeaders.set("authorization", `Bearer ${token}`);
  }

  const init: RequestInit = {
    method,
    headers: upstreamHeaders,
    cache: "no-store",
    /** Do not follow 30x to frontend-only paths on the API host (e.g. `/offertes/...`) — that can surface as 403/404 to the client. */
    redirect: "manual",
  };

  if (method !== "GET" && method !== "HEAD") {
    const body = await request.arrayBuffer();
    if (body.byteLength > 0) {
      init.body = body;
    }
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(targetUrl, init);
  } catch {
    return NextResponse.json({ detail: "Backend unreachable" }, { status: 502 });
  }

  const responseHeaders = new Headers();
  const responseContentType = backendResponse.headers.get("content-type");
  if (responseContentType) {
    responseHeaders.set("content-type", responseContentType);
  }
  const contentDisposition = backendResponse.headers.get("content-disposition");
  if (contentDisposition) {
    responseHeaders.set("content-disposition", contentDisposition);
  }
  const location = backendResponse.headers.get("location");
  if (location) {
    responseHeaders.set("location", location);
  }

  return new NextResponse(backendResponse.body, {
    status: backendResponse.status,
    statusText: backendResponse.statusText,
    headers: responseHeaders,
  });
}

type RouteContext = { params: Promise<{ path?: string[] }> };

export async function GET(request: NextRequest, ctx: RouteContext) {
  return proxyRequest(request, ctx.params);
}

export async function HEAD(request: NextRequest, ctx: RouteContext) {
  return proxyRequest(request, ctx.params);
}

export async function POST(request: NextRequest, ctx: RouteContext) {
  return proxyRequest(request, ctx.params);
}

export async function PUT(request: NextRequest, ctx: RouteContext) {
  return proxyRequest(request, ctx.params);
}

export async function PATCH(request: NextRequest, ctx: RouteContext) {
  return proxyRequest(request, ctx.params);
}

export async function DELETE(request: NextRequest, ctx: RouteContext) {
  return proxyRequest(request, ctx.params);
}
