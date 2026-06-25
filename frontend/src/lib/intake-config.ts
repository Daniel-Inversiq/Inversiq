import type { Sector } from "@/lib/tenant";

export type IntakeFieldConfig = {
  key: string;
  label: string;
  type: "text" | "textarea" | "number" | "select" | "file";
  required?: boolean;
  options?: { value: string; label: string }[];
  placeholder?: string;
};

export type VerticalIntakeConfig = {
  title: string;
  workflow: string[];
  fields: IntakeFieldConfig[];
};

export const VERTICAL_INTAKE_CONFIG: Record<Sector, VerticalIntakeConfig> = {
  construction: {
    title: "Submit a construction request",
    workflow: ["intake", "review", "estimate"],
    fields: [
      {
        key: "job_type",
        label: "Work type",
        type: "select",
        required: true,
        options: [
          { value: "interior", label: "Interior" },
          { value: "exterior", label: "Exterior" },
          { value: "both", label: "Interior & exterior" },
          { value: "structural", label: "Structural" },
          { value: "fit_out", label: "Fit-out" },
        ],
      },
      { key: "square_meters", label: "Area (m²)", type: "number", required: true },
      { key: "project_description", label: "Project description", type: "textarea", required: true },
    ],
  },
  insurance: {
    title: "Submit an insurance claim",
    workflow: ["intake", "assessment", "decision"],
    fields: [
      { key: "claim_type", label: "Claim type", type: "text", required: true },
      { key: "incident_date", label: "Incident date", type: "text", required: true },
      { key: "project_description", label: "Description", type: "textarea", required: true },
    ],
  },
  logistics: {
    title: "Submit a logistics request",
    workflow: ["intake", "routing", "dispatch"],
    fields: [
      { key: "origin", label: "Origin", type: "text", required: true },
      { key: "destination", label: "Destination", type: "text", required: true },
      { key: "project_description", label: "Description", type: "textarea", required: true },
    ],
  },
  real_estate: {
    title: "Submit a real estate request",
    workflow: ["intake", "valuation", "report"],
    fields: [
      { key: "property_type", label: "Property type", type: "text", required: true },
      { key: "address", label: "Address", type: "text", required: true },
      { key: "project_description", label: "Description", type: "textarea", required: true },
    ],
  },
};

export function getIntakeConfigForSector(sector: Sector | null | undefined): VerticalIntakeConfig {
  return VERTICAL_INTAKE_CONFIG[(sector ?? "construction") as Sector] ?? VERTICAL_INTAKE_CONFIG.construction;
}
