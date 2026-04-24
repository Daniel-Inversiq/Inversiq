import { NextResponse } from "next/server";
import { buildBackendUrl, getFrontendAccessTokenCookie } from "../_shared";

export async function GET(request: Request) {
  const token = getFrontendAccessTokenCookie(request);
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const backendResponse = await fetch(buildBackendUrl("/auth/me"), {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });

  const rawBody = await backendResponse.text();
  const contentType = backendResponse.headers.get("content-type") ?? "application/json";
  return new NextResponse(rawBody, {
    status: backendResponse.status,
    headers: { "content-type": contentType },
  });
}
