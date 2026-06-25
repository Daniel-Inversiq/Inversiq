"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertCircle, Check, CreditCard, ExternalLink, HelpCircle } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useSessionContext } from "@/components/shared/session-provider";
import { useBillingState } from "@/hooks/use-billing-state";
import { ApiError } from "@/lib/api/client";
import { postBillingPortal, postBillingTopup, postBillingUpgrade } from "@/lib/api/billing";
import { t } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { BillingPlanRow, BillingState } from "@/types/billing";

/** Billing-only CTA hierarchy: one strong primary, soft plan actions, neutral text links */
const billingCtaPrimaryClass =
  "h-8 rounded-md font-semibold bg-primary text-primary-foreground shadow-sm hover:bg-[color:var(--primary-hover)] active:bg-[color:var(--primary-hover)]";
const billingCtaSecondaryClass =
  "h-8 rounded-md border border-primary/30 bg-white font-semibold text-primary shadow-none hover:bg-primary/10 hover:text-[color:var(--primary-hover)] active:bg-primary/12";
const billingCtaTertiaryLinkClass =
  "text-[13px] font-semibold text-zinc-600 underline-offset-4 hover:text-zinc-900 hover:underline";
const billingCtaTertiaryButtonClass =
  "h-8 gap-1 bg-transparent font-semibold text-zinc-600 shadow-none hover:bg-transparent hover:text-zinc-900";

/** Primary dashboard sheet: matches dashboard/page.tsx DashboardSurface */
function DashboardSurface({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-[12px] border border-zinc-300/85 bg-white p-3 shadow-[0_1px_2px_rgba(15,23,42,0.04)] sm:p-4">
      {children}
    </div>
  );
}

function billingSubtitle(data: BillingState) {
  if (data.is_paid_or_trialing) {
    let s = `${data.current_plan_name} · ${data.subscription_status_label}`;
    if (data.subscription_status === "trialing" && data.trial_days_left != null) {
      const days = data.trial_days_left;
      const dayWord =
        days === 1 ? t("billing.trial.remaining_days", { days }) : t("billing.trial.remaining_days_plural", { days });
      s += ` · ${dayWord}`;
    }
    return s;
  }
  return t("billing.page.subtitle_inactive");
}

function planCtaLabel(plan: BillingPlanRow, isCurrent: boolean, paidOrTrialing: boolean) {
  if (isCurrent) {
    return t("billing.page.cta_current_plan");
  }
  if (!paidOrTrialing && plan.code !== "scale") {
    return t("billing.page.cta_start_with", { name: plan.name });
  }
  return plan.cta_label;
}

function usagePct(used: number, limit: number | null) {
  if (!limit || limit <= 0) {
    return 0;
  }
  return Math.min(100, Math.floor((used / limit) * 100));
}

function UsageBar({ pct }: { pct: number }) {
  const tone =
    pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-primary/80" : "bg-primary";
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-100">
      <div className={cn("h-1.5 rounded-full transition-all", tone)} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function BillingPageContent() {
  const session = useSessionContext();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const queryString = searchParams.toString();
  const qc = useQueryClient();

  const [portalBusy, setPortalBusy] = useState(false);
  const [upgradeBusy, setUpgradeBusy] = useState<string | null>(null);
  const [topupBusy, setTopupBusy] = useState(false);
  const topupFromQueryStarted = useRef(false);

  const canLoad = session.isAuthenticated;
  const billingQuery = useBillingState(queryString, canLoad);

  const checkoutStatus = searchParams.get("checkout");
  const topupStatus = searchParams.get("topup");

  const refetchBilling = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ["billing", "state"] });
  }, [qc]);

  const startTopup = useCallback(async () => {
    if (topupBusy) {
      return;
    }
    setTopupBusy(true);
    try {
      const data = await postBillingTopup();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
        return;
      }
      window.alert(t("billing.js.invalid_server_url"));
    } catch (e) {
      let message = t("billing.page.topup_failed");
      if (e instanceof ApiError) {
        const d = e.message;
        if (d.includes("not configured") || d.includes("Top-up price")) {
          message = t("billing.page.topup_not_configured");
        } else if (d) {
          message = `${t("billing.page.topup_failed")}: ${d}`;
        }
      }
      window.alert(message);
    } finally {
      setTopupBusy(false);
    }
  }, [topupBusy]);

  useEffect(() => {
    if (searchParams.get("action") !== "topup" || topupFromQueryStarted.current) {
      return;
    }
    topupFromQueryStarted.current = true;
    const qs = new URLSearchParams(searchParams.toString());
    qs.delete("action");
    const q = qs.toString();
    window.history.replaceState({}, "", q ? `${pathname}?${q}` : pathname);
    void startTopup();
  }, [pathname, searchParams, startTopup]);

  useEffect(() => {
    if (checkoutStatus === "success" || topupStatus === "success") {
      refetchBilling();
    }
  }, [checkoutStatus, topupStatus, refetchBilling]);

  const openBillingPortal = async () => {
    if (portalBusy) {
      return;
    }
    setPortalBusy(true);
    try {
      const data = await postBillingPortal();
      if (data.portal_url) {
        window.location.href = data.portal_url;
        return;
      }
      window.alert(t("billing.js.invalid_portal_url"));
    } catch (e) {
      if (e instanceof ApiError && e.status === 400 && e.message === "no_customer") {
        router.replace(`${pathname}?portal_error=no_customer`);
        refetchBilling();
        return;
      }
      window.alert(t("billing.js.portal_open_failed"));
    } finally {
      setPortalBusy(false);
    }
  };

  const upgradePlan = async (planCode: string) => {
    if (upgradeBusy) {
      return;
    }
    setUpgradeBusy(planCode);
    try {
      const data = await postBillingUpgrade(planCode);
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
        return;
      }
      if (data.redirect_url) {
        window.location.href = data.redirect_url;
        return;
      }
      window.alert(t("billing.js.invalid_server_url"));
    } catch (e) {
      let message = t("billing.js.upgrade_failed");
      if (e instanceof ApiError && e.message) {
        message = t("billing.js.upgrade_failed_with_detail", { detail: e.message });
      }
      window.alert(message);
    } finally {
      setUpgradeBusy(null);
    }
  };

  const data = billingQuery.data;

  const usage = data?.billing_offer_usage ?? null;
  const pct = useMemo(() => {
    if (!usage || usage.unlimited || !usage.limit_for_plan) {
      return 0;
    }
    return usagePct(usage.used_this_month, usage.limit_for_plan);
  }, [usage]);

  if (session.isLoading) {
    return (
      <DashboardSurface>
        <div className="space-y-3">
          <Skeleton className="h-6 w-48 rounded-md bg-zinc-100/90" />
          <Skeleton className="h-4 w-full max-w-lg rounded-md bg-zinc-100/85" />
          <div className="grid gap-2 lg:grid-cols-12">
            <Skeleton className="h-40 rounded-[11px] bg-zinc-100/80 lg:col-span-8" />
            <Skeleton className="h-40 rounded-[11px] bg-zinc-100/80 lg:col-span-4" />
          </div>
        </div>
      </DashboardSurface>
    );
  }

  if (!session.isAuthenticated) {
    return (
      <DashboardSurface>
        <Alert variant="destructive">
          <AlertTitle>{t("common.auth.not_logged_in")}</AlertTitle>
          <AlertDescription>{t("customers.errors.not_logged_in_description")}</AlertDescription>
        </Alert>
      </DashboardSurface>
    );
  }

  if (billingQuery.isError) {
    return (
      <DashboardSurface>
        <Alert variant="destructive">
          <AlertTitle>{t("dashboard.operational.errors.load_failed_title")}</AlertTitle>
          <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <p>{t("dashboard.operational.errors.load_failed_description")}</p>
            <Button variant="outline" size="sm" onClick={() => void billingQuery.refetch()}>
              {t("common.actions.retry")}
            </Button>
          </AlertDescription>
        </Alert>
      </DashboardSurface>
    );
  }

  if (!data) {
    return (
      <DashboardSurface>
        <div className="space-y-3">
          <Skeleton className="h-6 w-48 rounded-md bg-zinc-100/90" />
          <Skeleton className="h-4 w-full max-w-lg rounded-md bg-zinc-100/85" />
        </div>
      </DashboardSurface>
    );
  }

  const paid = data.is_paid_or_trialing;

  return (
    <DashboardSurface>
      <div className="space-y-2.5">
        {checkoutStatus === "success" ? (
          <Alert className="border-zinc-200/80 bg-white text-zinc-900">
            <Check className="size-4 text-primary" aria-hidden />
            <AlertTitle className="text-[13px] font-semibold">{t("billing.page.checkout_success_title")}</AlertTitle>
            <AlertDescription className="text-[13px] text-zinc-700">
              {t("billing.page.checkout_success_body")}
            </AlertDescription>
          </Alert>
        ) : null}
        {checkoutStatus === "cancel" ? (
          <Alert className="border-zinc-200/80 bg-zinc-50/80">
            <AlertTitle className="text-[13px] font-semibold">{t("billing.page.checkout_cancel_title")}</AlertTitle>
            <AlertDescription className="text-[13px] text-zinc-700">
              {t("billing.page.checkout_cancel_body")}
            </AlertDescription>
          </Alert>
        ) : null}
        {topupStatus === "success" ? (
          <Alert className="border-zinc-200/80 bg-white text-zinc-900">
            <Check className="size-4 text-primary" aria-hidden />
            <AlertTitle className="text-[13px] font-semibold">{t("billing.page.topup_success_title")}</AlertTitle>
            <AlertDescription className="text-[13px] text-zinc-700">
              {t("billing.page.topup_success_body")}
            </AlertDescription>
          </Alert>
        ) : null}

        {data.billing_status_error ? (
          <Alert className="border-[#4A7C59]/30 bg-[#EEF4F0]">
            <AlertCircle className="size-4 text-[#4A7C59]" aria-hidden />
            <AlertDescription className="text-[13px] text-zinc-900">{t("billing.errors.inactive_subscription")}</AlertDescription>
          </Alert>
        ) : null}
        {data.portal_error_no_customer ? (
          <Alert className="border-[#4A7C59]/30 bg-[#EEF4F0]">
            <AlertCircle className="size-4 text-[#4A7C59]" aria-hidden />
            <AlertDescription className="text-[13px] text-zinc-900">{t("billing.errors.no_customer")}</AlertDescription>
          </Alert>
        ) : null}

        <header className="flex flex-col gap-1.5 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
          <div className="min-w-0 space-y-1">
            <p className="type-eyebrow text-zinc-600">{t("billing.page.kicker")}</p>
            <h1 className="type-page-title">{data.title}</h1>
            <p className="max-w-2xl text-[13px] font-medium leading-[1.5] text-zinc-600">{billingSubtitle(data)}</p>
          </div>
          {!paid ? (
            <Link
              href="#plan-comparison"
              className={cn(
                "inline-flex shrink-0 items-center justify-center rounded-md px-3 text-[13px] motion-interactive",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 focus-visible:ring-offset-2",
                billingCtaSecondaryClass,
              )}
            >
              {t("billing.page.choose_plan_cta")}
            </Link>
          ) : null}
        </header>

        <div className="grid grid-cols-1 gap-2 lg:grid-cols-12 lg:items-start">
          <div className="min-w-0 space-y-2 lg:col-span-8">
            <section className="overflow-hidden rounded-[11px] border border-zinc-300/85 bg-white">
              <div className="border-b border-zinc-300/75 px-3 py-2.5">
                <h2 className="text-[13px] font-semibold tracking-[-0.01em] text-zinc-950">
                  {t("billing.page.section_current")}
                </h2>
              </div>
              <div className="grid grid-cols-2 divide-x divide-zinc-300/75 sm:grid-cols-4">
                <div className="px-3 py-3 sm:px-4 sm:py-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-zinc-600">{t("billing.labels.current_plan")}</p>
                  <p className="mt-1.5 text-[13px] font-semibold text-zinc-950">{data.current_plan_name}</p>
                </div>
                <div className="px-3 py-3 sm:px-4 sm:py-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-zinc-600">{t("billing.labels.status")}</p>
                  <div className="mt-1.5">
                    {data.subscription_status === "trialing" ? (
                      <Badge variant="outline" className="border-[#4A7C59]/30 bg-[#EEF4F0] text-zinc-900">
                        {data.subscription_status_label}
                      </Badge>
                    ) : data.subscription_status === "active" ? (
                      <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
                        {data.subscription_status_label}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-zinc-700">
                        {data.subscription_status_label}
                      </Badge>
                    )}
                  </div>
                </div>
                <div className="px-3 py-3 sm:px-4 sm:py-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-zinc-600">{t("billing.page.price_label")}</p>
                  <div className="mt-1.5">
                    {paid ? (
                      <p className="text-[13px] font-semibold text-zinc-950">{data.current_plan_price_label}</p>
                    ) : (
                      <span className="text-[13px] text-zinc-500">—</span>
                    )}
                  </div>
                </div>
                <div className="px-3 py-3 sm:px-4 sm:py-4">
                  {data.subscription_status === "trialing" && data.trial_days_left != null ? (
                    <>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-zinc-600">{t("billing.labels.trial")}</p>
                      <p className="mt-1.5 text-[13px] font-semibold text-zinc-950">
                        {data.trial_days_left === 1
                          ? t("billing.trial.remaining_days", { days: data.trial_days_left })
                          : t("billing.trial.remaining_days_plural", { days: data.trial_days_left })}
                      </p>
                      {data.trial_ends_at_display ? (
                        <p className="mt-0.5 text-[11px] text-zinc-500">
                          {t("billing.trial.until_date", { date: data.trial_ends_at_display })}
                        </p>
                      ) : null}
                    </>
                  ) : paid ? (
                    <>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-zinc-600">{t("billing.page.billing_manage")}</p>
                      <button
                        type="button"
                        onClick={() => void openBillingPortal()}
                        className={cn("mt-1.5 text-left", billingCtaTertiaryLinkClass)}
                      >
                        {t("billing.page.portal_link")}
                      </button>
                    </>
                  ) : (
                    <>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-zinc-600">{t("billing.page.get_started")}</p>
                      <Link
                        href="#plan-comparison"
                        className={cn("mt-1.5 inline-block", billingCtaTertiaryLinkClass)}
                      >
                        {t("billing.page.choose_plan_link")}
                      </Link>
                    </>
                  )}
                </div>
              </div>
            </section>

            {usage ? (
              <section className="overflow-hidden rounded-[11px] border border-zinc-300/85 bg-white">
                <div className="flex items-center justify-between gap-3 border-b border-zinc-300/75 px-3 py-2.5">
                  <h2 className="text-[13px] font-semibold text-zinc-950">{t("billing.page.section_usage")}</h2>
                  {usage.unlimited ? (
                    <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
                      {t("billing.page.unlimited_badge")}
                    </Badge>
                  ) : null}
                </div>
                <div className="px-3 py-3 sm:px-4 sm:py-4">
                  {usage.unlimited ? (
                    <p className="text-[13px] font-medium text-zinc-700">{usage.usage_text_nl}</p>
                  ) : usage.limit_for_plan ? (
                    <>
                      <div className="flex items-end justify-between gap-4">
                        <div className="min-w-0 flex-1">
                          <div className="mb-1.5 flex justify-between text-[11px] font-medium text-zinc-600">
                            <span>
                              {t("billing.page.usage_used", { n: usage.used_this_month })}
                            </span>
                            <span>
                              {t("billing.page.usage_max", { n: usage.limit_for_plan })}
                            </span>
                          </div>
                          <UsageBar pct={pct} />
                        </div>
                        <div className="shrink-0 text-right">
                          <p className="text-[12px] font-semibold tabular-nums text-zinc-800">
                            {t("billing.page.usage_remaining", { n: usage.remaining_this_month ?? 0 })}
                          </p>
                        </div>
                      </div>
                      {usage.usage_warning_nl || pct >= 90 ? (
                        <Alert className="mt-3 border-[#4A7C59]/30 bg-[#EEF4F0] py-2">
                          <AlertDescription className="text-[12px] text-zinc-900">
                            {pct >= 100
                              ? t("billing.page.usage_hard_cap")
                              : pct >= 90
                                ? t("billing.page.usage_near_cap", { n: usage.remaining_this_month ?? 0 })
                                : usage.usage_warning_nl}
                          </AlertDescription>
                        </Alert>
                      ) : null}
                    </>
                  ) : null}
                </div>
              </section>
            ) : null}

            <section id="plan-comparison" className="overflow-hidden rounded-[11px] border border-zinc-300/85 bg-white">
              <div className="flex items-center justify-between gap-3 border-b border-zinc-300/75 px-3 py-2.5">
                <h2 className="text-[13px] font-semibold text-zinc-950">{t("billing.labels.pricing_heading")}</h2>
                <span className="text-[11px] font-medium text-zinc-500">{t("billing.page.ex_vat")}</span>
              </div>
              <div className="divide-y divide-zinc-300/75">
                {data.plans.map((plan) => {
                  const isCurrent = plan.code === data.current_plan_code && paid;
                  const isRecommended = plan.is_recommended;
                  return (
                    <div
                      key={plan.code}
                      className={cn(
                        "flex flex-col gap-4 px-3 py-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6 sm:px-4",
                        isRecommended ? "bg-zinc-50/80" : "bg-white",
                      )}
                    >
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-[13px] font-semibold text-zinc-950">{plan.name}</span>
                          {isCurrent ? (
                            <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
                              {t("billing.labels.current_plan_badge")}
                            </Badge>
                          ) : null}
                          {isRecommended && !isCurrent ? (
                            <Badge variant="secondary">{t("billing.labels.recommended")}</Badge>
                          ) : null}
                        </div>
                        {plan.tagline ? <p className="text-[12px] text-zinc-500">{plan.tagline}</p> : null}
                        <p className="text-[12px] font-medium text-zinc-600">{plan.quote_limit_label}</p>
                        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                          {plan.features.map((feat) => (
                            <li key={feat} className="flex items-center gap-1.5 text-[12px] text-zinc-600">
                              <Check className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
                              {feat}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div className="shrink-0 text-right sm:pt-0">
                        <p className="text-[22px] font-semibold tabular-nums tracking-[-0.03em] text-zinc-950">{plan.price_display}</p>
                        <p className="text-[11px] text-zinc-500">{t("billing.page.per_month_suffix")}</p>
                        <div className="mt-3">
                          {isCurrent ? (
                            <Button type="button" size="sm" variant="outline" disabled className="h-8 rounded-md">
                              {planCtaLabel(plan, true, paid)}
                            </Button>
                          ) : (
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              className={cn(
                                billingCtaSecondaryClass,
                                "focus-visible:ring-2 focus-visible:ring-primary/20 focus-visible:ring-offset-2",
                              )}
                              disabled={upgradeBusy !== null}
                              onClick={() => void upgradePlan(plan.code)}
                            >
                              {upgradeBusy === plan.code ? "…" : planCtaLabel(plan, false, paid)}
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="border-t border-zinc-300/75 px-3 py-2.5 text-[11px] text-zinc-500 sm:px-4">
                {paid ? (
                  <p>
                    {t("billing.labels.prices_ex_vat_prefix")}{" "}
                    <button type="button" className={billingCtaTertiaryLinkClass} onClick={() => void openBillingPortal()}>
                      {t("billing.cta.manage_subscription")}
                    </button>
                    {t("billing.labels.prices_ex_vat_suffix")}
                  </p>
                ) : (
                  <p>{t("billing.page.footer_vat_only")}</p>
                )}
              </div>
            </section>

            {paid ? (
              <section className="overflow-hidden rounded-[11px] border border-zinc-300/85 bg-white">
                <div className="flex items-center justify-between gap-3 border-b border-zinc-300/75 px-3 py-2.5">
                  <h2 className="text-[13px] font-semibold text-zinc-950">{t("billing.page.section_topup")}</h2>
                  <Badge variant="secondary">{t("billing.page.topup_badge")}</Badge>
                </div>
                <div className="flex flex-col gap-3 px-3 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-4">
                  <p className="min-w-0 text-[13px] font-medium leading-[1.5] text-zinc-700">{t("billing.page.topup_description")}</p>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 shrink-0"
                    disabled={topupBusy}
                    onClick={() => void startTopup()}
                  >
                    {topupBusy ? "…" : t("billing.page.topup_cta")}
                  </Button>
                </div>
              </section>
            ) : null}
          </div>

          <aside className="flex min-w-0 flex-col gap-2 lg:col-span-4">
            <section className="overflow-hidden rounded-[11px] border border-zinc-300/85 bg-white">
              <div className="border-b border-zinc-300/75 px-3 py-2.5">
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-zinc-300/85 bg-zinc-50 text-zinc-600">
                    <CreditCard className="h-3.5 w-3.5" aria-hidden />
                  </span>
                  <div>
                    <h2 className="text-[13px] font-semibold text-zinc-950">{t("common.subscription")}</h2>
                    <p className="mt-0.5 text-[12px] font-medium text-zinc-600">{t("billing.page.aside_subscription_hint")}</p>
                  </div>
                </div>
              </div>
              <div className="space-y-3 px-3 py-3 sm:px-4">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-zinc-600">{t("billing.labels.current_plan")}</p>
                  <p className="mt-1 text-[13px] font-semibold text-zinc-950">{data.current_plan_name}</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-zinc-600">{t("billing.labels.status")}</p>
                  <div className="mt-1">
                    {data.subscription_status === "trialing" ? (
                      <Badge variant="outline" className="border-[#4A7C59]/30 bg-[#EEF4F0] text-zinc-900">
                        {data.subscription_status_label}
                      </Badge>
                    ) : data.subscription_status === "active" ? (
                      <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
                        {data.subscription_status_label}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-zinc-700">
                        {data.subscription_status_label}
                      </Badge>
                    )}
                  </div>
                </div>
                {data.subscription_status === "trialing" && data.trial_days_left != null ? (
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-zinc-600">{t("billing.labels.trial")}</p>
                    <p className="mt-1 text-[13px] font-semibold text-zinc-950">
                      {data.trial_days_left === 1
                        ? t("billing.trial.remaining_days", { days: data.trial_days_left })
                        : t("billing.trial.remaining_days_plural", { days: data.trial_days_left })}
                    </p>
                    {data.trial_ends_at_display ? (
                      <p className="mt-0.5 text-[11px] text-zinc-500">{t("billing.page.trial_ends", { date: data.trial_ends_at_display })}</p>
                    ) : null}
                  </div>
                ) : null}
                <div className="border-t border-zinc-300/75 pt-3">
                  {paid ? (
                    <Button
                      type="button"
                      className={cn("w-full", billingCtaPrimaryClass)}
                      disabled={portalBusy}
                      onClick={() => void openBillingPortal()}
                    >
                      {portalBusy ? "…" : t("billing.cta.manage_subscription")}
                    </Button>
                  ) : (
                    <>
                      <Link
                        href="#plan-comparison"
                        className={cn(
                          "inline-flex w-full items-center justify-center rounded-md text-[13px] motion-interactive",
                          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 focus-visible:ring-offset-2",
                          billingCtaSecondaryClass,
                        )}
                      >
                        {t("billing.page.choose_plan_cta")}
                      </Link>
                      <p className="mt-2 text-[11px] text-zinc-500">{t("billing.page.aside_inactive_hint")}</p>
                    </>
                  )}
                </div>
              </div>
            </section>

            {usage && !usage.unlimited && usage.limit_for_plan ? (
              <section className="overflow-hidden rounded-[11px] border border-zinc-300/85 bg-white">
                <div className="border-b border-zinc-300/75 px-3 py-2.5">
                  <h2 className="text-[13px] font-semibold text-zinc-950">{t("billing.page.aside_usage_title")}</h2>
                </div>
                <div className="px-3 py-3 sm:px-4">
                  <div className="flex items-end justify-between gap-2">
                    <div>
                      <span className="text-[22px] font-semibold tabular-nums text-zinc-950">{usage.used_this_month}</span>
                      <span className="text-[13px] font-medium text-zinc-500">/{usage.limit_for_plan}</span>
                    </div>
                    <p className="text-[11px] font-medium text-zinc-600">
                      {t("billing.page.usage_remaining", { n: usage.remaining_this_month ?? 0 })}
                    </p>
                  </div>
                  <div className="mt-2.5">
                    <UsageBar pct={pct} />
                  </div>
                  <p className="mt-1 text-[10px] font-medium text-zinc-500">{t("billing.page.usage_pct_label", { pct })}</p>
                </div>
              </section>
            ) : null}

            <section className="overflow-hidden rounded-[11px] border border-zinc-300/85 bg-white px-3 py-3 sm:px-4">
              <div className="flex items-start gap-2">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-zinc-300/85 bg-zinc-50 text-zinc-600">
                  <HelpCircle className="h-3.5 w-3.5" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-zinc-600">{t("billing.page.help_title")}</p>
                  <p className="mt-2 text-[13px] font-medium leading-[1.5] text-zinc-700">
                    {paid ? t("billing.page.help_active") : t("billing.page.help_inactive")}
                  </p>
                  {paid ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className={cn("mt-2.5 h-8 justify-start gap-1 px-0", billingCtaTertiaryButtonClass)}
                      disabled={portalBusy}
                      onClick={() => void openBillingPortal()}
                    >
                      {t("billing.page.help_invoice_cta")}
                      <ExternalLink className="h-3 w-3" aria-hidden />
                    </Button>
                  ) : null}
                </div>
              </div>
            </section>
          </aside>
        </div>
      </div>
    </DashboardSurface>
  );
}
