import { getBackendHref } from "@/lib/api/origin";

type OfferteEditPageProps = {
  params: Promise<{ quoteId: string }>;
};

export default async function OfferteEditPage({ params }: OfferteEditPageProps) {
  const { quoteId } = await params;
  const backendEditHref = getBackendHref(`/app/leads/${encodeURIComponent(quoteId)}/edit-estimate`);
  return (
    <div className="mx-auto w-full max-w-[min(1480px,100%)] space-y-2.5">
      <header className="space-y-1">
        <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">Offerte bewerken</p>
        <h1 className="text-[22px] font-semibold leading-tight tracking-[-0.02em] text-zinc-950">Bewerkmodus</h1>
      </header>
      <div className="overflow-hidden rounded-xl border border-zinc-200/75 bg-white p-3 shadow-[0_1px_0_rgba(15,23,42,0.03)] sm:p-3.5">
        <iframe
          title={`Offerte ${quoteId} bewerken`}
          src={backendEditHref}
          className="h-[calc(100vh-220px)] min-h-[680px] w-full border-0"
        />
      </div>
    </div>
  );
}
