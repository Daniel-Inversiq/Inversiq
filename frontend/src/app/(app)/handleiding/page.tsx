"use client";

import { PageHeader } from "@/components/ui/page-header";
import { t } from "@/lib/i18n";

const SECTIONS = [
  { titleKey: "guide_page.s1.title", itemKeys: ["guide_page.s1.i1", "guide_page.s1.i2"] as const },
  { titleKey: "guide_page.s2.title", itemKeys: ["guide_page.s2.i1", "guide_page.s2.i2", "guide_page.s2.i3"] as const },
  { titleKey: "guide_page.s3.title", itemKeys: ["guide_page.s3.i1", "guide_page.s3.i2"] as const },
  { titleKey: "guide_page.s4.title", itemKeys: ["guide_page.s4.i1", "guide_page.s4.i2"] as const },
] as const;

export default function HandleidingPage() {
  return (
    <div className="mx-auto w-full max-w-2xl px-1 pb-10 pt-1 sm:px-0">
      <PageHeader
        className="mb-8"
        title={t("guide_page.title")}
        description={t("guide_page.subtitle")}
      />

      <div className="space-y-4">
        {SECTIONS.map((section) => (
          <section
            key={section.titleKey}
            className="rounded-xl border border-zinc-200/75 bg-white p-4 shadow-[0_1px_0_rgba(15,23,42,0.03)] sm:p-5"
          >
            <h2 className="text-[15px] font-semibold tracking-[-0.02em] text-zinc-950">
              {t(section.titleKey)}
            </h2>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-[13px] font-medium leading-relaxed text-zinc-600 marker:text-zinc-300">
              {section.itemKeys.map((key) => (
                <li key={key}>{t(key)}</li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
