"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { RequireAuth } from "@/components/shared/require-auth";
import { ApiError } from "@/lib/api/client";
import { updateTenantSector } from "@/lib/tenant";
import { APP_ROUTES } from "@/lib/routes";

type SectorOption = {
  value: "construction" | "insurance" | "logistics" | "real_estate";
  label: string;
  subtitle: string;
};

const SECTOR_OPTIONS: SectorOption[] = [
  { value: "construction", label: "Construction", subtitle: "Live" },
  { value: "insurance",    label: "Insurance",    subtitle: "Preview" },
  { value: "logistics",    label: "Logistics",    subtitle: "Preview" },
  { value: "real_estate",  label: "Real Estate",  subtitle: "Preview" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [savingSector, setSavingSector] = useState<SectorOption["value"] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSelectSector(sector: SectorOption["value"]) {
    setError(null);
    setSavingSector(sector);
    try {
      await updateTenantSector(sector);
      router.replace(APP_ROUTES.dashboard);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError("Je sessie is verlopen. Log opnieuw in.");
        } else {
          setError(err.message || "Opslaan is mislukt. Probeer opnieuw.");
        }
      } else {
        setError("Opslaan is mislukt. Probeer opnieuw.");
      }
      setSavingSector(null);
    }
  }

  const isSaving = savingSector !== null;

  return (
    <RequireAuth>
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-zinc-50 px-4 py-10 dark:bg-zinc-950">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(1000px_500px_at_50%_-10%,rgba(2,6,23,0.06),transparent)] dark:bg-[radial-gradient(1000px_500px_at_50%_-10%,rgba(255,255,255,0.05),transparent)]"
        />
        <div className="relative w-full max-w-[720px]">
          <p className="mb-4 text-center text-sm font-medium tracking-tight text-zinc-600 dark:text-zinc-400">
            Inversiq
          </p>
          <Card className="w-full rounded-2xl border-zinc-200/80 shadow-sm dark:border-zinc-800">
            <CardHeader className="space-y-2 px-7 pb-2 pt-7">
              <CardTitle className="text-2xl tracking-tight">Select your industry</CardTitle>
              <CardDescription className="text-sm text-zinc-600 dark:text-zinc-400">
                We'll configure your workspace for the right operational context.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5 px-7 pb-7">
              {error ? (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              ) : null}

              <div className="grid gap-3 sm:grid-cols-3">
                {SECTOR_OPTIONS.map((option) => {
                  const selectedAndSaving = savingSector === option.value;
                  return (
                    <Button
                      key={option.value}
                      type="button"
                      variant="outline"
                      className="h-auto min-h-[92px] flex-col items-start justify-start gap-1 rounded-xl p-4 text-left"
                      disabled={isSaving}
                      onClick={() => void handleSelectSector(option.value)}
                    >
                      <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                        {option.label}
                      </span>
                      <span className="text-xs text-zinc-500">{option.subtitle}</span>
                      {selectedAndSaving ? (
                        <span className="mt-2 inline-flex items-center gap-2 text-xs text-zinc-600">
                          <span
                            className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
                            aria-hidden="true"
                          />
                          Saving...
                        </span>
                      ) : null}
                    </Button>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </RequireAuth>
  );
}
