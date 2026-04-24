import { apiRequest } from "@/lib/api/client";
import { getPreferredLanguage } from "@/lib/i18n";
import type { BillingState } from "@/types/billing";

function acceptLanguageHeader(): Record<string, string> {
  const lang = getPreferredLanguage();
  return {
    "Accept-Language": lang === "nl" ? "nl,nl-NL;q=0.9,en;q=0.8" : "en,en-US;q=0.9,nl;q=0.8",
  };
}

export async function fetchBillingState(queryString: string) {
  const qs = queryString && queryString.length > 0 ? `?${queryString}` : "";
  return apiRequest<BillingState>(`/app/api/billing${qs}`, {
    headers: acceptLanguageHeader(),
  });
}

export async function postBillingPortal() {
  return apiRequest<{ portal_url: string }>("/app/billing/portal", {
    method: "POST",
    body: JSON.stringify({}),
    headers: acceptLanguageHeader(),
  });
}

export async function postBillingUpgrade(planCode: string) {
  return apiRequest<{ checkout_url?: string; redirect_url?: string }>(
    `/app/billing/upgrade/${encodeURIComponent(planCode)}`,
    {
      method: "POST",
      body: JSON.stringify({}),
      headers: acceptLanguageHeader(),
    },
  );
}

export async function postBillingTopup() {
  return apiRequest<{ checkout_url: string }>("/app/billing/topup", {
    method: "POST",
    body: JSON.stringify({}),
    headers: acceptLanguageHeader(),
  });
}
