import Link from "next/link";
import { ActivityItem, ActivityPayload } from "@/types/dashboard";
import { formatDateTime } from "@/lib/presentation";
import { t } from "@/lib/i18n";
import { getBackendHref } from "@/lib/api/origin";

type ActivityFeedProps = {
  activity: ActivityPayload;
};

export function ActivityFeed({ activity }: ActivityFeedProps) {
  const ATTENTION_EVENTS = new Set(["review_required", "processing_failed"]);
  const NEW_REQUEST_EVENTS = new Set(["new_intake_request"]);
  const COMPLETED_EVENTS = new Set(["quote_ready"]);
  const LEAD_EVENTS = new Set([
    "new_intake_request",
    "review_required",
    "processing_failed",
  ]);

  const getLeadIdFromUrl = (url: string | null): string | null => {
    if (!url) {
      return null;
    }
    const match = url.match(/\/(?:quotes|app\/leads|customers)\/([^/?#]+)/i);
    return match?.[1] ?? null;
  };

  const getActionLink = (item: ActivityItem): { href: string; label: string } | null => {
    const normalized = item.event_type.trim().toLowerCase();
    const leadId = getLeadIdFromUrl(item.link_url);

    if (LEAD_EVENTS.has(normalized)) {
      return {
        href: leadId ? `/customers/${leadId}` : "/customers",
        label: t("dashboard.activity.actions.open_lead"),
      };
    }

    if (normalized === "quote_ready") {
      return {
        href: leadId ? getBackendHref(`/quotes/${leadId}/html`) : "/quotes",
        label: t("dashboard.activity.actions.view_send_quote"),
      };
    }

    if (item.link_url) {
      return {
        href: item.link_url,
        label: t("dashboard.activity.open_item"),
      };
    }

    return null;
  };

  const eventTypeLabel = (eventType: string) => {
    const normalized = eventType.trim().toLowerCase();
    const key = `dashboard.activity.event_type.${normalized}`;
    const translated = t(key);
    return translated === key ? eventType.replace(/_/g, " ") : translated;
  };

  const groups = {
    attention: activity.items.filter((item) =>
      ATTENTION_EVENTS.has(item.event_type.trim().toLowerCase()),
    ),
    newRequests: activity.items.filter((item) =>
      NEW_REQUEST_EVENTS.has(item.event_type.trim().toLowerCase()),
    ),
    completed: activity.items.filter((item) =>
      COMPLETED_EVENTS.has(item.event_type.trim().toLowerCase()),
    ),
  };

  const hasOperationalHighlights =
    groups.attention.length > 0 ||
    groups.newRequests.length > 0 ||
    groups.completed.length > 0;

  const renderEventRow = (item: ActivityItem) => {
    const actionLink = getActionLink(item);
    return (
      <div key={item.id} className="border-b border-zinc-100 py-2 last:border-b-0">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold leading-[1.45] text-zinc-900">{item.title}</p>
            <p className="type-meta mt-0.5 capitalize text-zinc-600">{eventTypeLabel(item.event_type)}</p>
          </div>
          <time className="type-meta shrink-0 text-zinc-600">
            {formatDateTime(item.created_at)}
          </time>
        </div>
        {actionLink ? (
          <Link
            href={actionLink.href}
            target={actionLink.href.startsWith("http") ? "_blank" : undefined}
            rel={actionLink.href.startsWith("http") ? "noopener noreferrer" : undefined}
            className="mt-1.5 inline-flex text-[13px] font-semibold text-primary transition-colors hover:text-primary/80"
          >
            {actionLink.label}
          </Link>
        ) : null}
      </div>
    );
  };

  const renderOperationalGroup = (
    titleKey: string,
    descriptionKey: string,
    items: ActivityItem[],
  ) => {
    if (items.length === 0) {
      return null;
    }

    return (
      <section className="rounded-lg border border-zinc-200/90 bg-zinc-50/50 p-2.5">
        <div className="flex items-center justify-between gap-3">
          <h3 className="type-eyebrow text-zinc-700">{t(titleKey)}</h3>
          <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-semibold tabular-nums text-zinc-700">
            {items.length}
          </span>
        </div>
        <p className="type-body-secondary mt-0.5 text-zinc-600">{t(descriptionKey)}</p>
        <div className="mt-2 space-y-1">{items.slice(0, 3).map(renderEventRow)}</div>
      </section>
    );
  };

  return (
    <section className="space-y-2.5">
      <header className="space-y-0">
        <p className="type-eyebrow text-zinc-600">{t("dashboard.activity.kicker")}</p>
        <h2 className="type-section-title mt-0.5">{t("dashboard.activity.title")}</h2>
        <p className="type-body-secondary mt-0.5 text-zinc-600">{t("dashboard.activity.subtitle")}</p>
      </header>
      {activity.items.length === 0 ? (
        <div className="rounded-lg border border-zinc-200/80 bg-white py-4 pl-4 pr-3 text-left">
          <p className="type-body-secondary text-zinc-600">{t("dashboard.activity.empty")}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {hasOperationalHighlights ? (
            <div className="space-y-2">
              {renderOperationalGroup(
                "dashboard.activity.groups.needs_attention.title",
                "dashboard.activity.groups.needs_attention.description",
                groups.attention,
              )}
              {renderOperationalGroup(
                "dashboard.activity.groups.new_requests.title",
                "dashboard.activity.groups.new_requests.description",
                groups.newRequests,
              )}
              {renderOperationalGroup(
                "dashboard.activity.groups.recently_completed.title",
                "dashboard.activity.groups.recently_completed.description",
                groups.completed,
              )}
            </div>
          ) : null}
          <div className="rounded-lg border border-zinc-200/85 bg-white/80 p-2.5">
            <h3 className="type-eyebrow text-zinc-700">{t("dashboard.activity.timeline_title")}</h3>
            <div className="mt-2 space-y-1.5">
              {activity.items.map(renderEventRow)}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
