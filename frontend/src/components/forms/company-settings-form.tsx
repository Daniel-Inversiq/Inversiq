"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Upload } from "lucide-react";
import { useCompanySettings } from "@/hooks/use-company-settings";
import { updateCompanySettings, uploadCompanyLogo } from "@/lib/api/settings";
import { useSessionContext } from "@/components/shared/session-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { t } from "@/lib/i18n";

type CompanySettingsValues = {
  companyName: string;
  supportEmail: string;
  pricePerM2: string;
};

export function CompanySettingsForm() {
  const session = useSessionContext();
  const settingsQuery = useCompanySettings(session.isAuthenticated);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoMessage, setLogoMessage] = useState<string | null>(null);
  const [logoError, setLogoError] = useState<string | null>(null);
  const [isUploadingLogo, setIsUploadingLogo] = useState(false);
  const logoPreviewUrl = useMemo(() => {
    if (logoFile) {
      return URL.createObjectURL(logoFile);
    }
    return settingsQuery.data?.logo_url ?? null;
  }, [logoFile, settingsQuery.data?.logo_url]);

  const companySettingsSchema = useMemo(
    () =>
      z.object({
        companyName: z.string().min(2, t("settings.validation.company_name_required")),
        supportEmail: z.email(t("settings.validation.support_email_invalid")),
        pricePerM2: z
          .string()
          .trim()
          .refine(
            (value) => value === "" || /^[0-9]+([.,][0-9]{1,2})?$/.test(value),
            t("settings.validation.price_per_m2_invalid"),
          ),
      }),
    [],
  );

  const form = useForm<CompanySettingsValues>({
    resolver: zodResolver(companySettingsSchema),
    defaultValues: {
      companyName: "",
      supportEmail: "",
      pricePerM2: "",
    },
  });

  useEffect(() => {
    if (!settingsQuery.data) {
      return;
    }
    form.reset({
      companyName: settingsQuery.data.company_name || "",
      supportEmail: settingsQuery.data.support_email || "",
      pricePerM2:
        settingsQuery.data.price_per_m2 !== null &&
        settingsQuery.data.price_per_m2 !== undefined
          ? String(settingsQuery.data.price_per_m2)
          : "",
    });
  }, [form, settingsQuery.data]);

  useEffect(() => {
    if (!logoFile || !logoPreviewUrl?.startsWith("blob:")) {
      return;
    }
    return () => URL.revokeObjectURL(logoPreviewUrl);
  }, [logoFile, logoPreviewUrl]);

  const parsePricePerM2 = (raw: string): number | null => {
    const normalized = raw.trim().replace(",", ".");
    if (!normalized) {
      return null;
    }
    const parsed = Number.parseFloat(normalized);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      throw new Error("invalid_price_per_m2");
    }
    return parsed;
  };

  const onSubmit = async (values: CompanySettingsValues) => {
    setSaveMessage(null);
    setSaveError(null);
    try {
      const pricePerM2 = parsePricePerM2(values.pricePerM2);
      await updateCompanySettings(values.companyName, pricePerM2);
      setSaveMessage(t("settings.feedback.saved"));
      settingsQuery.refetch();
    } catch (error) {
      if (error instanceof Error && error.message === "invalid_price_per_m2") {
        form.setError("pricePerM2", {
          type: "validate",
          message: t("settings.validation.price_per_m2_invalid"),
        });
        return;
      }
      setSaveError(t("settings.feedback.save_failed"));
    }
  };

  const onUploadLogo = async () => {
    if (!logoFile) {
      setLogoError(t("settings.feedback.logo_select_first"));
      return;
    }
    setLogoMessage(null);
    setLogoError(null);
    setIsUploadingLogo(true);
    try {
      await uploadCompanyLogo(logoFile);
      setLogoMessage(t("settings.feedback.logo_saved"));
      setLogoFile(null);
      await settingsQuery.refetch();
    } catch {
      setLogoError(t("settings.feedback.logo_upload_failed"));
    } finally {
      setIsUploadingLogo(false);
    }
  };

  if (session.isLoading || (settingsQuery.isLoading && !settingsQuery.data)) {
    return (
      <div className="rounded-xl border bg-white p-6">
        <h1 className="text-xl font-semibold text-slate-900">{t("settings.header.title")}</h1>
        <div className="mt-2">
          <p className="text-sm text-muted-foreground">{t("settings.loading")}</p>
        </div>
      </div>
    );
  }

  if (!session.isAuthenticated) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("common.auth.not_logged_in")}</AlertTitle>
        <AlertDescription>{t("settings.errors.not_logged_in_description")}</AlertDescription>
      </Alert>
    );
  }

  if (settingsQuery.error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("settings.errors.load_failed_title")}</AlertTitle>
        <AlertDescription>
          {t("settings.errors.load_failed_description")}
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <form className="space-y-8" onSubmit={form.handleSubmit(onSubmit)} noValidate>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            {t("settings.header.title")}
          </h1>
          <p className="text-sm text-slate-500">{t("settings.form.support_email_hint")}</p>
        </div>
        <Button type="submit" disabled={form.formState.isSubmitting} className="min-w-52 shrink-0">
          {form.formState.isSubmitting ? t("settings.form.saving") : "Wijzigingen opslaan"}
        </Button>
      </div>

      <section className="space-y-4 rounded-xl border bg-white p-6">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold text-slate-900">Bedrijf</h2>
          <p className="text-sm text-slate-500">Basisgegevens en branding van je bedrijf.</p>
        </div>

        <div className="max-w-md space-y-2">
          <Label htmlFor="companyName" className="text-xs font-medium text-slate-500">
            {t("settings.form.company_name")}
          </Label>
          <Input id="companyName" {...form.register("companyName")} />
          {form.formState.errors.companyName ? (
            <p className="text-xs text-destructive">
              {form.formState.errors.companyName.message}
            </p>
          ) : null}
        </div>

        <div className="max-w-md space-y-2">
          <Label htmlFor="supportEmail" className="text-xs font-medium text-slate-500">
            {t("settings.form.support_email")}
          </Label>
          <Input id="supportEmail" {...form.register("supportEmail")} disabled />
          {form.formState.errors.supportEmail ? (
            <p className="text-xs text-destructive">
              {form.formState.errors.supportEmail.message}
            </p>
          ) : null}
        </div>

        <div className="space-y-3">
          <div className="max-w-md space-y-1">
            <Label htmlFor="logoFile" className="text-xs font-medium text-slate-500">
              {t("settings.form.company_logo")}
            </Label>
            <input
              id="logoFile"
              type="file"
              accept="image/png,image/jpeg"
              className="sr-only"
              onChange={(event) => setLogoFile(event.target.files?.[0] ?? null)}
            />
            <label
              htmlFor="logoFile"
              className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-slate-300 bg-slate-50/50 px-4 py-7 text-center transition-colors duration-150 hover:border-primary/40 hover:bg-slate-50"
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-white text-slate-500 shadow-sm">
                <Upload className="h-4 w-4" aria-hidden />
              </span>
              <p className="text-sm font-medium text-slate-700">
                Klik om logo te uploaden of sleep hier
              </p>
              <p className="text-xs text-slate-500">PNG of JPG, maximaal 5MB</p>
            </label>
          </div>

          {logoPreviewUrl ? (
            <div className="space-y-2">
              <p className="text-xs font-medium text-slate-500">Preview</p>
              <img
                src={logoPreviewUrl}
                alt={t("settings.form.company_logo")}
                className="h-16 w-auto rounded-md border border-slate-200 bg-white p-2"
              />
            </div>
          ) : (
            <p className="text-xs text-slate-500">{t("settings.form.no_logo")}</p>
          )}

          <Button
            type="button"
            variant="outline"
            disabled={isUploadingLogo}
            onClick={onUploadLogo}
          >
            {isUploadingLogo ? t("settings.form.uploading_logo") : t("settings.form.upload_logo")}
          </Button>
          {logoMessage ? <p className="text-xs text-primary">{logoMessage}</p> : null}
          {logoError ? <p className="text-xs text-destructive">{logoError}</p> : null}
        </div>
      </section>

      <section className="space-y-4 rounded-xl border bg-white p-6">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold text-slate-900">{t("settings.pricing.title")}</h2>
          <p className="text-sm text-slate-500">Stel je standaardtarief in voor calculaties.</p>
        </div>

        <div className="max-w-md space-y-2">
          <Label htmlFor="pricePerM2" className="text-xs font-medium text-slate-500">
            {t("settings.pricing.price_per_m2_label")}
          </Label>
          <div className="flex items-center gap-2 rounded-md border border-input bg-background px-3">
            <span className="text-sm text-muted-foreground">€</span>
            <Input
              id="pricePerM2"
              type="number"
              step="0.01"
              min="0"
              inputMode="decimal"
              className="border-0 px-0 shadow-none focus-visible:ring-0"
              placeholder={t("settings.pricing.price_per_m2_placeholder")}
              {...form.register("pricePerM2")}
            />
            <span className="text-sm text-muted-foreground">/m²</span>
          </div>
          {form.formState.errors.pricePerM2 ? (
            <p className="text-xs text-destructive">
              {form.formState.errors.pricePerM2.message}
            </p>
          ) : null}
          <p className="text-xs text-muted-foreground">
            {t("settings.pricing.price_per_m2_help")}
          </p>
        </div>
      </section>

      {(saveMessage || saveError) && (
        <div className="rounded-xl border bg-white p-4">
          {saveMessage ? <p className="text-xs text-primary">{saveMessage}</p> : null}
          {saveError ? <p className="text-xs text-destructive">{saveError}</p> : null}
        </div>
      )}
    </form>
  );
}
