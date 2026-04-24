"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useCompanySettings } from "@/hooks/use-company-settings";
import { updateCompanySettings, uploadCompanyLogo } from "@/lib/api/settings";
import { useSessionContext } from "@/components/shared/session-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.header.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{t("settings.loading")}</p>
        </CardContent>
      </Card>
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
    <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.header.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="companyName">{t("settings.form.company_name")}</Label>
            <Input id="companyName" {...form.register("companyName")} />
            {form.formState.errors.companyName ? (
              <p className="text-xs text-destructive">
                {form.formState.errors.companyName.message}
              </p>
            ) : null}
          </div>
          <div className="space-y-2">
            <Label htmlFor="supportEmail">{t("settings.form.support_email")}</Label>
            <Input id="supportEmail" {...form.register("supportEmail")} disabled />
            {form.formState.errors.supportEmail ? (
              <p className="text-xs text-destructive">
                {form.formState.errors.supportEmail.message}
              </p>
            ) : null}
            <p className="text-xs text-muted-foreground">
              {t("settings.form.support_email_hint")}
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="logoFile">{t("settings.form.company_logo")}</Label>
            {settingsQuery.data?.logo_url ? (
              <a
                href={settingsQuery.data?.logo_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex text-xs font-medium text-primary hover:text-primary/80"
              >
                {t("settings.form.open_current_logo")}
              </a>
            ) : (
              <p className="text-xs text-muted-foreground">
                {t("settings.form.no_logo")}
              </p>
            )}
            <Input
              id="logoFile"
              type="file"
              accept="image/png,image/jpeg"
              onChange={(event) => setLogoFile(event.target.files?.[0] ?? null)}
            />
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
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.pricing.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="pricePerM2">{t("settings.pricing.price_per_m2_label")}</Label>
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
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-6">
          <Button
            type="submit"
            disabled={form.formState.isSubmitting}
            className="min-w-40"
          >
            {form.formState.isSubmitting ? t("settings.form.saving") : t("settings.form.save")}
          </Button>
          {saveMessage ? <p className="text-xs text-primary">{saveMessage}</p> : null}
          {saveError ? <p className="text-xs text-destructive">{saveError}</p> : null}
        </CardContent>
      </Card>
    </form>
  );
}
