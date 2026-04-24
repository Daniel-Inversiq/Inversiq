import { apiRequest } from "@/lib/api/client";
import { CompanySettingsResponse } from "@/types/settings";

export function fetchCompanySettings() {
  return apiRequest<CompanySettingsResponse>("/app/settings/company");
}

export function updateCompanySettings(companyName: string, pricePerM2: number | null) {
  return apiRequest<{ success: boolean }>("/settings/company", {
    method: "POST",
    body: JSON.stringify({
      company_name: companyName,
      price_per_m2: pricePerM2,
    }),
  });
}

export async function uploadCompanyLogo(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/settings/logo", {
    method: "POST",
    credentials: "include",
    body: formData,
  });

  if (!response.ok) {
    const payload = await response.text();
    throw new Error(payload || `Logo upload failed (${response.status})`);
  }

  return (await response.json()) as { logo_url: string };
}
