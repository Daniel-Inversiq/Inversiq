import { NextResponse } from "next/server";
import { buildBackendUrl, parseAccessTokenFromSetCookie, setFrontendAuthCookie } from "../_shared";

type RegisterPayloadInput = {
  company_name?: unknown;
  companyName?: unknown;
  email?: unknown;
  phone?: unknown;
  walls_rate_eur_per_sqm?: unknown;
  wallsRateEurPerSqm?: unknown;
  password?: unknown;
};

function normalizeRegisterPayload(payload: unknown): Record<string, unknown> {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return {};
  }
  const input = payload as RegisterPayloadInput;
  return {
    ...input,
    company_name: input.company_name ?? input.companyName,
    walls_rate_eur_per_sqm:
      input.walls_rate_eur_per_sqm ?? input.wallsRateEurPerSqm,
  };
}

export async function POST(request: Request) {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid registration payload" }, { status: 422 });
  }

  const backendResponse = await fetch(buildBackendUrl("/auth/register"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(normalizeRegisterPayload(payload)),
    cache: "no-store",
  });

  const rawBody = await backendResponse.text();
  const contentType = backendResponse.headers.get("content-type") ?? "application/json";
  if (!backendResponse.ok) {
    return new NextResponse(rawBody, {
      status: backendResponse.status,
      headers: { "content-type": contentType },
    });
  }

  const token = parseAccessTokenFromSetCookie(backendResponse.headers.get("set-cookie"));
  if (!token) {
    return NextResponse.json(
      { detail: "Registration succeeded but auth cookie was missing" },
      { status: 502 },
    );
  }

  const response = new NextResponse(rawBody, {
    status: backendResponse.status,
    headers: { "content-type": contentType },
  });
  setFrontendAuthCookie(response, token);
  return response;
}
