import { ReviewDetailView } from "@/components/reviews/review-detail-view";

type ReviewDetailPageProps = {
  params: Promise<{ leadId: string }>;
};

export default async function ReviewDetailPage({ params }: ReviewDetailPageProps) {
  const { leadId } = await params;
  return <ReviewDetailView leadId={leadId} />;
}
