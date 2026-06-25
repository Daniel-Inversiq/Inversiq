import { apiRequestSameOrigin } from "@/lib/api/client";

export type Sector = "construction" | "insurance" | "logistics" | "real_estate";

export type VerticalWorkflow = {
  id: string;
  use: string;
  on_needs_review?: string;
  with?: Record<string, unknown>;
};

export type VerticalFeatures = {
  measurements?: boolean;
  damage_assessment?: boolean;
  yield_estimation?: boolean;
} & Record<string, unknown>;

export type VerticalDashboardConfig = {
  show_kpis?: boolean;
  show_pipeline?: boolean;
  show_recent_jobs?: boolean;
} & Record<string, unknown>;

export type VerticalConfig = {
  key: string;
  label: string;
  workflows: VerticalWorkflow[];
  ui_workflows?: string[];
  engine_pipeline?: VerticalWorkflow[];
  features: VerticalFeatures;
  dashboard: VerticalDashboardConfig;
};

export type TenantMeResponse = {
  id: string;
  sector: Sector | null;
  onboarding_completed?: boolean;
  vertical: VerticalConfig;
};

function tenantProxyPath(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `/api/backend/tenant${normalizedPath}`;
}

export function getTenantMe() {
  return apiRequestSameOrigin<TenantMeResponse>(tenantProxyPath("/me"));
}

export function updateTenantSector(sector: Sector) {
  return apiRequestSameOrigin<TenantMeResponse>(tenantProxyPath("/sector"), {
    method: "PATCH",
    body: JSON.stringify({ sector }),
  });
}
