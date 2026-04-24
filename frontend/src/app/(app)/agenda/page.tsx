"use client";

import Link from "next/link";
import { type ReactNode, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useSessionContext } from "@/components/shared/session-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useJobs } from "@/hooks/use-jobs";
import { addDays, dateKeyLocal, scheduledDateKey, startOfWeekMonday } from "@/lib/agenda-week";
import { getPreferredLanguage, t, tStatus } from "@/lib/i18n";
import { formatDateTime } from "@/lib/presentation";
import { isExecutionFlowStatus } from "@/lib/product-flow";
import { cn } from "@/lib/utils";
import type { JobListItem } from "@/types/jobs";

function WorkspacePanel({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("surface-card overflow-hidden", className)}>{children}</div>;
}

function formatWeekRangeLabel(weekMonday: Date, lang: "nl" | "en"): string {
  const end = addDays(weekMonday, 6);
  const loc = lang === "nl" ? "nl-NL" : "en-US";
  const sameMonth =
    weekMonday.getMonth() === end.getMonth() && weekMonday.getFullYear() === end.getFullYear();
  if (sameMonth) {
    const startDay = weekMonday.toLocaleDateString(loc, { day: "numeric" });
    const endPart = end.toLocaleDateString(loc, { day: "numeric", month: "long", year: "numeric" });
    return `${startDay}–${endPart}`;
  }
  const a = weekMonday.toLocaleDateString(loc, { day: "numeric", month: "short", year: "numeric" });
  const b = end.toLocaleDateString(loc, { day: "numeric", month: "short", year: "numeric" });
  return `${a} – ${b}`;
}

function formatTimeShort(iso: string | null | undefined, lang: "nl" | "en"): string {
  if (!iso) {
    return "—";
  }
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return "—";
  }
  const loc = lang === "nl" ? "nl-NL" : "en-US";
  return d.toLocaleTimeString(loc, { hour: "2-digit", minute: "2-digit" });
}

function formatDayTitle(day: Date, lang: "nl" | "en"): string {
  const loc = lang === "nl" ? "nl-NL" : "en-US";
  const weekday = day.toLocaleDateString(loc, { weekday: "long" });
  const rest = day.toLocaleDateString(loc, { day: "numeric", month: "short" });
  return `${weekday} ${rest}`;
}

/** Short weekday (e.g. ma / Mon) for compact column headers. */
function weekdayShortLabel(day: Date, lang: "nl" | "en"): string {
  const loc = lang === "nl" ? "nl-NL" : "en-US";
  return day.toLocaleDateString(loc, { weekday: "short" });
}

function DayColumnHeader({
  day,
  isToday,
  lang,
}: {
  day: Date;
  isToday: boolean;
  lang: "nl" | "en";
}) {
  const loc = lang === "nl" ? "nl-NL" : "en-US";
  const wd = weekdayShortLabel(day, lang);
  const dayNum = day.getDate();
  const month = day.toLocaleDateString(loc, { month: "short" });
  return (
    <div
      className={cn(
        "shrink-0 border-b px-1 py-1 text-left sm:px-1.5 sm:py-1.5",
        isToday ? "border-primary/25 bg-primary/[0.08]" : "border-zinc-200/80 bg-white",
      )}
      aria-label={formatDayTitle(day, lang)}
    >
      <p
        className={cn(
          "text-[9px] font-semibold uppercase leading-none tracking-[0.1em]",
          isToday ? "text-primary" : "text-zinc-400",
        )}
      >
        {wd}
      </p>
      <div className="mt-0.5 flex items-baseline gap-0.5">
        <span
          className={cn(
            "text-[16px] font-semibold tabular-nums leading-none sm:text-[17px]",
            isToday ? "text-primary" : "text-zinc-950",
          )}
        >
          {dayNum}
        </span>
        <span
          className={cn(
            "text-[10px] font-medium capitalize leading-none",
            isToday ? "text-primary/85" : "text-zinc-500",
          )}
        >
          {month}
        </span>
      </div>
    </div>
  );
}

function CompactJobCard({
  job,
  lang,
  formatTimeShort: formatTime,
}: {
  job: JobListItem;
  lang: "nl" | "en";
  formatTimeShort: (iso: string | null | undefined, lang: "nl" | "en") => string;
}) {
  const time = formatTime(job.scheduled_at, lang);
  return (
    <div className="rounded border border-zinc-200/85 bg-white p-1 shadow-[0_1px_0_rgba(15,23,42,0.02)]">
      <div className="flex items-start justify-between gap-0.5">
        <span className="shrink-0 text-[11px] font-bold tabular-nums leading-none tracking-tight text-zinc-800">
          {time}
        </span>
        <StatusBadge
          status={job.status}
          className="h-[18px] shrink-0 px-1 py-0 text-[9px] leading-none"
        >
          {tStatus(job.status)}
        </StatusBadge>
      </div>
      <p className="mt-0.5 line-clamp-2 text-[11px] font-semibold leading-snug text-zinc-900">{job.lead_name || t("jobs.table.unknown_customer")}</p>
      <div className="mt-1 flex items-center justify-between gap-1 border-t border-zinc-100 pt-0.5">
        <span className="min-w-0 truncate text-[9px] font-medium text-zinc-400">
          {t("agenda_page.card.ref", { id: String(job.id) })}
        </span>
        <Link
          href={`/quotes/${job.lead_id}`}
          className="shrink-0 text-[10px] font-semibold text-primary hover:text-primary/85"
        >
          {t("jobs.actions.view_details")}
        </Link>
      </div>
    </div>
  );
}

function groupJobsByDayKey(jobs: JobListItem[]): Map<string, JobListItem[]> {
  const map = new Map<string, JobListItem[]>();
  for (const job of jobs) {
    const key = scheduledDateKey(job.scheduled_at);
    if (!key) {
      continue;
    }
    const list = map.get(key) ?? [];
    list.push(job);
    map.set(key, list);
  }
  for (const [, list] of map) {
    list.sort((a, b) => {
      const at = new Date(a.scheduled_at ?? 0).getTime();
      const bt = new Date(b.scheduled_at ?? 0).getTime();
      return at - bt;
    });
  }
  return map;
}

export default function AgendaPage() {
  const session = useSessionContext();
  const jobsQuery = useJobs(session.isAuthenticated);
  const lang = getPreferredLanguage() === "nl" ? "nl" : "en";

  const [weekMonday, setWeekMonday] = useState(() => startOfWeekMonday(new Date()));

  const scheduledJobs = useMemo(() => {
    return (jobsQuery.data ?? [])
      .filter((job) => Boolean(job.scheduled_at))
      .sort((a, b) => {
        const at = new Date(a.scheduled_at ?? 0).getTime();
        const bt = new Date(b.scheduled_at ?? 0).getTime();
        return at - bt;
      });
  }, [jobsQuery.data]);

  const unscheduledJobs = useMemo(() => {
    return (jobsQuery.data ?? []).filter(
      (job) => !job.scheduled_at && isExecutionFlowStatus(job.status),
    );
  }, [jobsQuery.data]);

  const byDay = useMemo(() => groupJobsByDayKey(scheduledJobs), [scheduledJobs]);

  const weekDayDates = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(weekMonday, i)), [weekMonday]);

  const weekKeySet = useMemo(() => new Set(weekDayDates.map((d) => dateKeyLocal(d))), [weekDayDates]);

  const jobsOutsideThisWeek = useMemo(() => {
    return scheduledJobs.filter((job) => {
      const k = scheduledDateKey(job.scheduled_at);
      return k && !weekKeySet.has(k);
    });
  }, [scheduledJobs, weekKeySet]);

  const now = Date.now();
  const upcoming = scheduledJobs.filter((job) => new Date(job.scheduled_at ?? 0).getTime() >= now);
  const past = scheduledJobs.filter((job) => new Date(job.scheduled_at ?? 0).getTime() < now);

  const todayKey = dateKeyLocal(new Date());

  if (session.isLoading || (jobsQuery.isLoading && !jobsQuery.data)) {
    return (
      <div className="mx-auto max-w-6xl space-y-2.5 pb-1">
        <div className="space-y-1.5">
          <Skeleton className="h-3 w-20 rounded bg-zinc-100/90 motion-reduce:animate-none" />
          <Skeleton className="h-7 w-52 rounded bg-zinc-100/90 motion-reduce:animate-none" />
          <Skeleton className="h-4 w-full max-w-md rounded bg-zinc-100/90 motion-reduce:animate-none" />
        </div>
        <Skeleton className="h-[42px] w-full rounded-[11px] bg-zinc-100/90 motion-reduce:animate-none" />
        <Skeleton className="h-[280px] w-full rounded-[12px] bg-zinc-100/90 motion-reduce:animate-none" />
      </div>
    );
  }

  if (!session.isAuthenticated) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("common.auth.not_logged_in")}</AlertTitle>
        <AlertDescription>{t("jobs.errors.not_logged_in_description")}</AlertDescription>
      </Alert>
    );
  }

  if (jobsQuery.error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("jobs.errors.load_failed_title")}</AlertTitle>
        <AlertDescription>
          <div className="space-y-3">
            <p>{t("jobs.errors.load_failed_description")}</p>
            <Button variant="outline" size="sm" onClick={() => void jobsQuery.refetch()}>
              {t("common.actions.retry")}
            </Button>
          </div>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <section className="mx-auto max-w-[min(100%,96rem)] space-y-3 pb-1">
      <header className="space-y-1.5">
        <p className="type-eyebrow text-zinc-400">{t("agenda_page.header.kicker")}</p>
        <h1 className="type-page-title text-zinc-950">{t("agenda_page.header.title")}</h1>
        <p className="max-w-2xl text-[13px] font-medium leading-snug text-zinc-500">
          {t("agenda_page.header.subtitle")}
        </p>
      </header>

      <div className="overflow-hidden rounded-[11px] border border-zinc-200/90 bg-white shadow-[0_1px_0_rgba(15,23,42,0.03)]">
        <div className="grid grid-cols-1 divide-y divide-zinc-200/85 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          {[
            { label: t("agenda_page.kpi.upcoming"), value: upcoming.length },
            { label: t("agenda_page.kpi.past"), value: past.length },
            { label: t("agenda_page.kpi.total"), value: scheduledJobs.length },
          ].map((item) => (
            <div
              key={item.label}
              className="flex min-h-[72px] flex-col justify-center gap-0.5 px-3 py-2.5 sm:min-h-0 sm:px-4 sm:py-3"
            >
              <p className="text-[10px] font-semibold uppercase leading-[14px] tracking-[0.06em] text-zinc-500">
                {item.label}
              </p>
              <p className="text-lg font-semibold leading-none tracking-[-0.03em] text-zinc-950 tabular-nums sm:text-xl">
                {item.value}
              </p>
            </div>
          ))}
        </div>
      </div>

      <WorkspacePanel>
        <div className="flex flex-col gap-2 border-b border-zinc-200/85 px-2.5 py-2 sm:flex-row sm:items-center sm:justify-between sm:px-3 sm:py-2.5">
          <p className="text-[12px] font-semibold tracking-tight text-zinc-900 sm:text-[13px]">
            {formatWeekRangeLabel(weekMonday, lang)}
          </p>
          <div className="flex flex-wrap items-center gap-1.5">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 border-zinc-200/90 bg-white px-2 text-zinc-700 shadow-none hover:bg-zinc-50"
              onClick={() => setWeekMonday((d) => addDays(d, -7))}
              aria-label={t("agenda_page.planner.prev_week_aria")}
            >
              <ChevronLeft className="size-4" />
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 border-zinc-200/90 bg-white px-2.5 text-[13px] font-semibold text-zinc-700 shadow-none hover:bg-zinc-50"
              onClick={() => setWeekMonday(startOfWeekMonday(new Date()))}
            >
              {t("agenda_page.planner.today")}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 border-zinc-200/90 bg-white px-2 text-zinc-700 shadow-none hover:bg-zinc-50"
              onClick={() => setWeekMonday((d) => addDays(d, 7))}
              aria-label={t("agenda_page.planner.next_week_aria")}
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>

        {scheduledJobs.length === 0 ? (
          <div className="space-y-3 px-2 py-3 sm:px-3 sm:py-4">
            <div className="rounded-lg border border-dashed border-zinc-200/90 bg-zinc-50/60 p-3 sm:p-3.5">
              <p className="type-section-title text-zinc-950">{t("agenda_page.empty.title")}</p>
              <p className="mt-1 text-[13px] font-medium leading-snug text-zinc-500">
                {t("agenda_page.empty.description")}
              </p>
              <p className="mt-1.5 text-[12px] font-medium leading-snug text-zinc-600">{t("agenda_page.empty.hint")}</p>
            </div>
            <div className="-mx-1 overflow-x-auto px-1 pb-0.5 sm:mx-0 sm:overflow-visible sm:px-0">
              <div className="grid w-full min-w-[720px] grid-cols-7 gap-px sm:min-w-0 sm:gap-0.5">
                {weekDayDates.map((day) => {
                  const dk = dateKeyLocal(day);
                  const isToday = dk === todayKey;
                  return (
                    <div
                      key={dk}
                      className={cn(
                        "flex min-h-[100px] min-w-0 flex-col rounded-md border",
                        isToday ? "border-primary/30 bg-primary/[0.05]" : "border-zinc-200/80 bg-zinc-50/40",
                      )}
                    >
                      <DayColumnHeader day={day} isToday={isToday} lang={lang} />
                      <div className="flex flex-1 items-center justify-center px-1 py-2">
                        <p className="text-center text-[10px] font-medium leading-tight text-zinc-400">
                          {t("agenda_page.day.empty")}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (
          <div className="px-1 py-1.5 sm:px-2 sm:py-2">
            <div className="-mx-1 overflow-x-auto px-1 pb-0.5 sm:mx-0 sm:overflow-visible sm:px-0">
              <div className="grid w-full min-w-[720px] grid-cols-7 gap-px sm:min-w-0 sm:gap-0.5">
                {weekDayDates.map((day) => {
                  const key = dateKeyLocal(day);
                  const dayJobs = byDay.get(key) ?? [];
                  const isToday = key === todayKey;
                  return (
                    <div
                      key={key}
                      className={cn(
                        "flex min-h-[200px] min-w-0 flex-col rounded-md border sm:min-h-[240px]",
                        isToday ? "border-primary/35 bg-primary/[0.04]" : "border-zinc-200/85 bg-zinc-50/30",
                      )}
                    >
                      <DayColumnHeader day={day} isToday={isToday} lang={lang} />
                      <div className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto overscroll-contain p-1">
                        {dayJobs.length === 0 ? (
                          <p className="px-0.5 py-2 text-center text-[10px] font-medium leading-tight text-zinc-400">
                            {t("agenda_page.day.empty")}
                          </p>
                        ) : (
                          dayJobs.map((job) => (
                            <CompactJobCard
                              key={job.id}
                              job={job}
                              lang={lang}
                              formatTimeShort={formatTimeShort}
                            />
                          ))
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </WorkspacePanel>

      {scheduledJobs.length > 0 && jobsOutsideThisWeek.length > 0 ? (
        <WorkspacePanel>
          <div className="border-b border-zinc-200/85 px-3 py-2.5 sm:px-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-zinc-500">
              {t("agenda_page.outside_week.title")}
            </p>
            <p className="mt-0.5 text-[12px] font-medium text-zinc-600">{t("agenda_page.outside_week.subtitle")}</p>
          </div>
          <ul className="divide-y divide-zinc-200/80 px-2 py-1 sm:px-3">
            {jobsOutsideThisWeek.map((job) => (
              <li key={job.id} className="flex flex-col gap-1 py-2.5 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                <div className="min-w-0">
                  <p className="truncate text-[13px] font-semibold text-zinc-950">
                    {job.lead_name || t("jobs.table.unknown_customer")}
                  </p>
                  <p className="text-[11px] font-medium text-zinc-500">
                    {t("agenda_page.card.ref", { id: String(job.id) })} · {formatDateTime(job.scheduled_at)}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <StatusBadge status={job.status}>{tStatus(job.status)}</StatusBadge>
                  <Link
                    href={`/quotes/${job.lead_id}`}
                    className="text-[12px] font-semibold text-primary hover:text-primary/85"
                  >
                    {t("jobs.actions.view_details")}
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        </WorkspacePanel>
      ) : null}

      {unscheduledJobs.length > 0 ? (
        <WorkspacePanel>
          <div className="border-b border-zinc-200/85 px-3 py-2.5 sm:px-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-zinc-500">
              {t("agenda_page.unscheduled.title")}
            </p>
            <p className="mt-0.5 text-[12px] font-medium text-zinc-600">{t("agenda_page.unscheduled.subtitle")}</p>
          </div>
          <ul className="divide-y divide-zinc-200/80 px-2 py-1 sm:px-3">
            {unscheduledJobs.map((job) => (
              <li key={job.id} className="flex flex-col gap-1 py-2.5 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                <div className="min-w-0">
                  <p className="truncate text-[13px] font-semibold text-zinc-950">
                    {job.lead_name || t("jobs.table.unknown_customer")}
                  </p>
                  <p className="text-[11px] font-medium text-zinc-500">
                    {t("agenda_page.card.ref", { id: String(job.id) })}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <StatusBadge status={job.status}>{tStatus(job.status)}</StatusBadge>
                  <Link
                    href={`/quotes/${job.lead_id}`}
                    className="text-[12px] font-semibold text-primary hover:text-primary/85"
                  >
                    {t("jobs.actions.view_details")}
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        </WorkspacePanel>
      ) : null}
    </section>
  );
}
