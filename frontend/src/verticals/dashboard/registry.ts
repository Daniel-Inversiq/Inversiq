import type { Sector } from "@/lib/tenant";
import ConstructionDashboardTools from "@/verticals/construction/components/dashboard-tools";
import type { SectorDashboardMetrics } from "@/verticals/dashboard/types";

export function renderSectorDashboard(sector: Sector, metrics: SectorDashboardMetrics) {
  switch (sector) {
    case "construction":
      return ConstructionDashboardTools({ metrics });
    case "insurance":
    case "logistics":
    case "real_estate":
      return null;
    default:
      return null;
  }
}
