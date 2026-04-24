"use client";

import Link from "next/link";
import { use, useEffect } from "react";
import { getBackendHref, getBackendOrigin } from "@/lib/api/origin";

type CustomerLeadPageProps = {
  params: Promise<{ leadId: string }>;
};

export default function CustomerLeadPage({ params }: CustomerLeadPageProps) {
  const { leadId } = use(params);
  const normalizedLeadId = String(leadId ?? "").trim();
  const href = normalizedLeadId
    ? getBackendHref(`/app/leads/${normalizedLeadId}`)
    : getBackendHref("/app/leads");

  useEffect(() => {
    if (!normalizedLeadId) {
      return;
    }
    window.location.assign(href);
  }, [href, normalizedLeadId]);

  return (
    <section className="space-y-3">
      <h1 className="type-page-title text-slate-900">Redirecting to lead detail</h1>
      <p className="text-sm text-slate-600">
        Forwarding to the backend lead page on {getBackendOrigin() || "configured API host"}.
      </p>
      <Link href={href} className="text-sm font-medium text-primary hover:text-primary/80">
        Open lead manually
      </Link>
    </section>
  );
}
