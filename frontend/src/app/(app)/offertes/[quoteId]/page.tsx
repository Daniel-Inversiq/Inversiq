import { OfferDetailView } from "@/components/offers/offer-detail-view";

type OfferteDetailPageProps = {
  params: Promise<{ quoteId: string }>;
};

export default async function OfferteDetailPage({ params }: OfferteDetailPageProps) {
  const { quoteId } = await params;
  return <OfferDetailView leadId={quoteId} />;
}
