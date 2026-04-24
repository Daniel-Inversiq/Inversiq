export type BillingPlanRow = {
  code: string;
  name: string;
  price_display: string;
  price_period: string;
  quote_limit_label: string;
  features: string[];
  tagline: string;
  is_recommended: boolean;
  cta_label: string;
};

export type BillingOfferUsage = {
  plan_code: string;
  used_this_month: number;
  limit_for_plan: number | null;
  remaining_this_month: number | null;
  unlimited: boolean;
  usage_text_nl: string;
  usage_warning_nl: string | null;
};

export type BillingState = {
  title: string;
  plans: BillingPlanRow[];
  current_plan_code: string;
  current_plan_name: string;
  current_plan_price_label: string;
  subscription_status: string;
  subscription_status_label: string;
  trial_days_left: number | null;
  trial_ends_at_display: string | null;
  trial_ends_at_iso: string | null;
  is_paid_or_trialing: boolean;
  billing_status_error: boolean;
  portal_error_no_customer: boolean;
  billing_offer_usage: BillingOfferUsage | null;
};
