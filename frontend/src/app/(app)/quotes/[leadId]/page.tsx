import { OfferDetailView } from "@/components/offers/offer-detail-view";

type OfferDetailPageProps = {
  params: Promise<{ leadId: string }>;
};

export default async function OfferDetailPage({ params }: OfferDetailPageProps) {
  const { leadId } = await params;
  return <OfferDetailView leadId={leadId} />;
}
