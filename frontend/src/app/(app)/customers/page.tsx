"use client";

import Link from "next/link";
import { Inbox } from "lucide-react";
import { useSessionContext } from "@/components/shared/session-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/ui/status-badge";
import { useTenantLeads } from "@/hooks/use-tenant-leads";
import { t, tStatus } from "@/lib/i18n";

function CustomersLoadingSkeleton() {
  return (
    <div className="app-page space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-3 w-24 rounded-md bg-zinc-100/90" />
        <Skeleton className="h-8 w-48 max-w-full rounded-md bg-zinc-100/90" />
        <Skeleton className="h-4 w-full max-w-lg rounded-md bg-zinc-100/90" />
      </div>
      <div className="surface-card h-[min(420px,55vh)] overflow-hidden p-4 sm:p-5">
        <Skeleton className="h-full w-full rounded-lg bg-zinc-100/75" />
      </div>
    </div>
  );
}

export default function CustomersPage() {
  const session = useSessionContext();
  const tenantId = session.user?.tenant_id?.trim() ?? "";
  const canLoadLeads = session.isAuthenticated && tenantId.length > 0;
  const leadsQuery = useTenantLeads(tenantId, canLoadLeads);
  const leads = leadsQuery.data ?? [];

  if (session.isLoading || leadsQuery.isLoading) {
    return <CustomersLoadingSkeleton />;
  }

  if (!session.isAuthenticated) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("common.auth.not_logged_in")}</AlertTitle>
        <AlertDescription>{t("customers.errors.not_logged_in_description")}</AlertDescription>
      </Alert>
    );
  }

  if (leadsQuery.error) {
    return (
      <div className="app-page">
        <Alert variant="destructive">
          <AlertTitle>{t("customers.errors.load_failed_title")}</AlertTitle>
          <AlertDescription>
            <div className="space-y-3">
              <p className="type-supporting">{t("customers.errors.load_failed_description")}</p>
              <Button variant="outline" size="sm" onClick={() => void leadsQuery.refetch()}>
                {t("common.actions.retry")}
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <section className="app-page">
      <PageHeader
        kicker={t("customers.header.kicker")}
        title={t("customers.header.title")}
        description={t("customers.header.subtitle")}
      />

      {leads.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={t("customers.empty.title")}
          description={t("customers.empty.description")}
        />
      ) : (
        <SectionCard padding="none" className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="border-zinc-200/85 hover:bg-transparent">
                <TableHead className="bg-zinc-50/90">{t("customers.table.name")}</TableHead>
                <TableHead className="bg-zinc-50/90">{t("customers.table.email")}</TableHead>
                <TableHead className="bg-zinc-50/90">{t("customers.table.status")}</TableHead>
                <TableHead className="bg-zinc-50/90 text-right">{t("customers.table.action")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {leads.map((lead) => (
                <TableRow key={lead.id}>
                  <TableCell className="font-semibold text-zinc-900">
                    {lead.name || t("common.states.unknown")}
                  </TableCell>
                  <TableCell className="text-zinc-600">{lead.email || "—"}</TableCell>
                  <TableCell>
                    <StatusBadge status={lead.status}>{tStatus(lead.status)}</StatusBadge>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        href={`/customers/${lead.id}`}
                        className={buttonVariants({ variant: "outline", size: "sm" })}
                      >
                        {t("customers.actions.open_lead")}
                      </Link>
                      <Link
                        href={`/quotes/${lead.id}`}
                        className={buttonVariants({ variant: "default", size: "sm" })}
                      >
                        {t("customers.actions.open_offer")}
                      </Link>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </SectionCard>
      )}
    </section>
  );
}
