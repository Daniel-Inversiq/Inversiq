import { redirect } from "next/navigation";
import { getBackendHref } from "@/lib/api/origin";

type OfferteEditAliasPageProps = {
  params: Promise<{ quoteId: string }>;
};

export default async function OfferteEditAliasPage({ params }: OfferteEditAliasPageProps) {
  const { quoteId } = await params;
  redirect(getBackendHref(`/app/leads/${encodeURIComponent(quoteId)}/edit-estimate`));
}
