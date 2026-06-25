"use client";

import { useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";

import { getDateLocale, t, tStatus } from "@/lib/i18n";

const INTAKE_DAY_CAP = 90;

/** Map backend `intake.series` (local calendar `day_key`) into chart points with locale labels. */
export function mapApiIntakeSeriesToChart(
  series: { day_key: string; count: number }[],
  rangeDays: number,
): { label: string; count: number; dayKey: string }[] {
  return series.map((s) => {
    const [y, m, d] = s.day_key.split("-").map(Number);
    const date = new Date(y, (m || 1) - 1, d || 1);
    const label =
      rangeDays <= 14
        ? date.toLocaleDateString(getDateLocale(), {
            weekday: "short",
            day: "numeric",
          })
        : date.toLocaleDateString(getDateLocale(), {
            day: "numeric",
            month: "short",
          });
    return { dayKey: s.day_key, count: s.count, label };
  });
}

/** Pipeline runs per calendar day — proxy for intake activity when lead timestamps are unavailable. */
export function buildIntakeSeriesFromRuns(
  runs: { created_at: string | null }[],
  dayCount = 7,
): { label: string; count: number; dayKey: string }[] {
  const n = Math.max(1, Math.min(INTAKE_DAY_CAP, Math.floor(dayCount)));
  const keys: string[] = [];
  const labels: string[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    keys.push(`${y}-${m}-${day}`);
    if (n <= 14) {
      labels.push(
        d.toLocaleDateString(getDateLocale(), {
          weekday: "short",
          day: "numeric",
        }),
      );
    } else {
      labels.push(
        d.toLocaleDateString(getDateLocale(), {
          day: "numeric",
          month: "short",
        }),
      );
    }
  }
  const counts = new Map(keys.map((k) => [k, 0]));
  for (const run of runs) {
    if (!run.created_at) {
      continue;
    }
    const t0 = new Date(run.created_at);
    const y = t0.getFullYear();
    const m = String(t0.getMonth() + 1).padStart(2, "0");
    const day = String(t0.getDate()).padStart(2, "0");
    const k = `${y}-${m}-${day}`;
    if (counts.has(k)) {
      counts.set(k, (counts.get(k) ?? 0) + 1);
    }
  }
  return keys.map((k, i) => ({ label: labels[i], count: counts.get(k) ?? 0, dayKey: k }));
}

type Point = { x: number; y: number; label: string; count: number };

/** Cubic bezier through points (Chart.js-style smoothing). */
function smoothLinePath(points: Point[]): string {
  if (points.length === 0) {
    return "";
  }
  if (points.length === 1) {
    return `M ${points[0].x} ${points[0].y}`;
  }
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(points.length - 1, i + 2)];
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
  }
  return d;
}

function smoothAreaPath(points: Point[], bottomY: number): string {
  if (points.length === 0) {
    return "";
  }
  const first = points[0];
  const last = points[points.length - 1];
  let d = `M ${first.x} ${bottomY} L ${first.x} ${first.y}`;
  if (points.length === 1) {
    d += ` L ${last.x} ${bottomY} Z`;
    return d;
  }
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(points.length - 1, i + 2)];
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
  }
  d += ` L ${last.x} ${bottomY} Z`;
  return d;
}

type IntakeChartSummary = {
  total: number;
  avg_per_day: number;
  zero_day_count: number;
  peak_day_key: string;
  peak_count: number;
  prior_range_total: number;
  prior_range_days: number;
};

type IntakeLineChartProps = {
  series: { label: string; count: number; dayKey: string }[];
  /** Used for accessibility + empty hint copy */
  dayRange?: number;
  /** When set, augments insight line (avg + vs prior period). */
  chartSummary?: IntakeChartSummary | null;
};

const LINE_STROKE = 2.25;
const CHART_LINE = "#4A7C59";
const CHART_DEEP = "#3D6B4A";
const ANIM_MS = 400;
/** SVG viewBox height — keep in sync with `h-[…px]` on the chart */
const CHART_VB_H = 264;

function formatTooltipDate(dayKey: string) {
  const [y, m, d] = dayKey.split("-").map(Number);
  if (!y || !m || !d) {
    return dayKey;
  }
  return new Date(y, m - 1, d).toLocaleDateString(getDateLocale(), {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

function weekdayNameLong(dayKey: string) {
  const [y, m, d] = dayKey.split("-").map(Number);
  if (!y || !m || !d) {
    return "";
  }
  return new Date(y, m - 1, d).toLocaleDateString(getDateLocale(), { weekday: "long" });
}

/** Y-axis labels + horizontal grid positions (t = fraction from bottom, 0 = baseline). */
function buildYAxisTicks(maxScale: number): { t: number; label: string }[] {
  if (maxScale <= 3) {
    return [
      { t: 1, label: String(maxScale) },
      { t: 0, label: "0" },
    ];
  }
  const hi = maxScale;
  return [
    { t: 1, label: String(hi) },
    { t: 0.66, label: String(Math.max(1, Math.round(hi * 0.66))) },
    { t: 0.33, label: String(Math.max(0, Math.round(hi * 0.33))) },
    { t: 0, label: "0" },
  ];
}

type IntakeSeriesPoint = { label: string; count: number; dayKey: string };

function IntakeChartInsights({
  series,
  dayRange,
  chartSummary,
}: {
  series: IntakeSeriesPoint[];
  dayRange: number;
  chartSummary?: IntakeChartSummary | null;
}) {
  const counts = series.map((s) => s.count);
  const sum = counts.reduce((a, b) => a + b, 0);
  let peakIdx = 0;
  let peakVal = -1;
  for (let i = 0; i < counts.length; i++) {
    if (counts[i] > peakVal) {
      peakVal = counts[i];
      peakIdx = i;
    }
  }
  const peakDayKey = series[peakIdx]?.dayKey ?? "";
  const peakWeekday = weekdayNameLong(peakDayKey);
  const zeroDays = counts.filter((c) => c === 0).length;

  const avgDisplay =
    chartSummary && chartSummary.avg_per_day > 0
      ? chartSummary.avg_per_day % 1 === 0
        ? String(chartSummary.avg_per_day)
        : chartSummary.avg_per_day.toFixed(1)
      : null;

  let vsPriorLine: string | null = null;
  if (chartSummary && sum > 0 && chartSummary.prior_range_days > 0) {
    const prev = chartSummary.prior_range_total;
    if (prev === 0) {
      vsPriorLine = t("dashboard.operational.chart.insight_vs_prior_baseline", {
        days: chartSummary.prior_range_days,
      });
    } else {
      const changePct = Math.round(((sum - prev) / prev) * 100);
      if (changePct > 0) {
        vsPriorLine = t("dashboard.operational.chart.insight_vs_prior_up", {
          pct: changePct,
          days: chartSummary.prior_range_days,
        });
      } else if (changePct < 0) {
        vsPriorLine = t("dashboard.operational.chart.insight_vs_prior_down", {
          pct: Math.abs(changePct),
          days: chartSummary.prior_range_days,
        });
      } else {
        vsPriorLine = t("dashboard.operational.chart.insight_vs_prior_flat", {
          days: chartSummary.prior_range_days,
        });
      }
    }
  }

  return (
    <div className="mt-2 border-t border-zinc-200 pt-2">
      <p className="text-[11px] font-semibold leading-snug text-zinc-800">
        {t("dashboard.operational.chart.insight_range", { days: dayRange })}
      </p>
      {sum === 0 ? (
        <p className="mt-1 text-[11px] leading-snug text-zinc-500">{t("dashboard.operational.chart.insight_none")}</p>
      ) : (
        <div className="mt-1.5 flex flex-col gap-1.5 text-[11px] leading-snug text-zinc-600">
          <p>
            {t("dashboard.operational.chart.insight_peak", {
              weekday: peakWeekday,
              count: peakVal,
            })}
            {avgDisplay ? (
              <>
                <span className="mx-1.5 inline text-zinc-300" aria-hidden>
                  ·
                </span>
                <span className="text-zinc-600">
                  {t("dashboard.operational.chart.insight_avg", { avg: avgDisplay })}
                </span>
              </>
            ) : null}
          </p>
          {zeroDays > 0 ? (
            <p className="text-zinc-500">
              {zeroDays === 1
                ? t("dashboard.operational.chart.insight_quiet_days_one")
                : t("dashboard.operational.chart.insight_quiet_days", { count: zeroDays })}
              {vsPriorLine ? (
                <>
                  <span className="mx-1.5 inline text-zinc-300" aria-hidden>
                    ·
                  </span>
                  <span>{vsPriorLine}</span>
                </>
              ) : null}
            </p>
          ) : vsPriorLine ? (
            <p className="text-zinc-500">{vsPriorLine}</p>
          ) : null}
        </div>
      )}
    </div>
  );
}

/** Premium line + area: brand green accent, subtle fill, hover tooltip, active point. */
export function IntakeLineChart({ series, dayRange = 7, chartSummary = null }: IntakeLineChartProps) {
  const w = 640;
  const h = CHART_VB_H;
  const padL = 38;
  const padR = 4;
  const padT = 16;
  const padB = 36;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;
  const counts = series.map((s) => s.count);
  const maxRaw = counts.length ? Math.max(...counts) : 0;
  const max = Math.max(1, maxRaw);
  const n = series.length;
  const step = n > 1 ? innerW / (n - 1) : 0;

  const points: Point[] = series.map((s, i) => {
    const x = n === 1 ? padL + innerW / 2 : padL + i * step;
    const y = padT + innerH - (s.count / max) * innerH;
    return { x, y, label: s.label, count: s.count };
  });

  const bottomY = padT + innerH;
  const lineD = smoothLinePath(points);
  const areaD = smoothAreaPath(points, bottomY);

  const lineRef = useRef<SVGPathElement | null>(null);
  const glowRef = useRef<SVGPathElement | null>(null);
  const [dash, setDash] = useState({ len: 0, ready: false });
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const gradId = useId().replace(/:/g, "");
  const areaGradId = `area-${gradId}`;

  const labelSkip = (() => {
    if (n <= 1) {
      return 1;
    }
    if (dayRange <= 7) {
      return 1;
    }
    if (dayRange <= 14) {
      return 2;
    }
    if (dayRange <= 30) {
      return 4;
    }
    return 7;
  })();

  useLayoutEffect(() => {
    const path = lineRef.current;
    if (!path || !lineD) {
      return;
    }
    const len = path.getTotalLength();
    setDash({ len, ready: false });
    path.style.strokeDasharray = `${len}`;
    path.style.strokeDashoffset = `${len}`;
    if (glowRef.current) {
      glowRef.current.style.strokeDasharray = `${len}`;
      glowRef.current.style.strokeDashoffset = `${len}`;
    }

    const reduceMotion =
      typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reduceMotion) {
      path.style.strokeDashoffset = "0";
      if (glowRef.current) {
        glowRef.current.style.strokeDashoffset = "0";
      }
      setDash({ len, ready: true });
      return;
    }

    const t0 = performance.now();
    let raf = 0;
    const ease = (t: number) => 1 - (1 - t) ** 3;

    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / ANIM_MS);
      const off = len * (1 - ease(p));
      path.style.strokeDashoffset = `${off}`;
      if (glowRef.current) {
        glowRef.current.style.strokeDashoffset = `${off}`;
      }
      if (p < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        setDash({ len, ready: true });
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [lineD]);

  const yTicks = buildYAxisTicks(max);
  const yAxisTickX = Math.max(10, padL - 8);

  const handleOverlayPointer = (clientX: number, svgEl: SVGSVGElement) => {
    if (n < 1) {
      return;
    }
    const rect = svgEl.getBoundingClientRect();
    const relX = ((clientX - rect.left) / rect.width) * w;
    const ix = n === 1 ? 0 : Math.round((relX - padL) / step);
    const idx = Math.max(0, Math.min(n - 1, ix));
    setActiveIndex(idx);
  };

  const handleChartKeyDown = (e: KeyboardEvent<SVGSVGElement>) => {
    if (n < 1) {
      return;
    }
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      setActiveIndex((prev) => {
        if (e.key === "ArrowRight") {
          const cur = prev === null ? -1 : prev;
          return Math.min(n - 1, cur + 1);
        }
        const cur = prev === null ? n : prev;
        return Math.max(0, cur - 1);
      });
    } else if (e.key === "Escape") {
      e.preventDefault();
      setActiveIndex(null);
    }
  };

  const ariaLabel = t("dashboard.operational.chart.aria_intake", { days: dayRange });
  const sumCounts = counts.reduce((a, b) => a + b, 0);
  const activePoint = activeIndex !== null ? points[activeIndex] : null;
  const activeDayKey = activeIndex !== null ? series[activeIndex]?.dayKey : "";
  const tooltipXPct = activePoint ? (activePoint.x / w) * 100 : 50;
  const tooltipTransform =
    tooltipXPct < 17 ? "translateX(0)" : tooltipXPct > 83 ? "translateX(-100%)" : "translateX(-50%)";

  if (n === 0) {
    return (
      <div className="flex min-h-[264px] w-full flex-col items-center justify-center rounded-xl border border-dashed border-zinc-200 bg-[#FFFFFF] px-4 py-6 text-center">
        <p className="max-w-[18rem] text-[12px] font-medium leading-relaxed text-zinc-500">
          {t("dashboard.operational.chart.empty_hint")}
        </p>
      </div>
    );
  }

  return (
    <div className="relative w-full">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="font-sans h-[264px] w-full max-w-full touch-none rounded-xl bg-[#FFFFFF] text-zinc-500 outline-none ring-offset-2 focus-visible:ring-2 focus-visible:ring-slate-300/60"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        tabIndex={0}
        aria-label={ariaLabel}
        onPointerLeave={() => setActiveIndex(null)}
        onKeyDown={handleChartKeyDown}
      >
        <defs>
          <linearGradient id={areaGradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART_LINE} stopOpacity="0.2" />
            <stop offset="45%" stopColor={CHART_DEEP} stopOpacity="0.09" />
            <stop offset="100%" stopColor={CHART_LINE} stopOpacity="0" />
          </linearGradient>
        </defs>

        <text
          x={0}
          y={0}
          transform={`translate(8 ${padT + innerH / 2}) rotate(-90)`}
          textAnchor="middle"
          style={{
            fontSize: "10.5px",
            fontWeight: 600,
            fontFamily: "inherit",
            fill: "#71717a",
            letterSpacing: "0.01em",
            pointerEvents: "none",
          }}
        >
          {t("dashboard.operational.chart.y_axis_label")}
        </text>

        {yTicks.map(({ t: gridT }) => {
          const y = padT + innerH * (1 - gridT);
          return (
            <line
              key={`grid-${gridT}`}
              x1={padL}
              x2={w - padR}
              y1={y}
              y2={y}
              stroke="#E5E7EB"
              strokeOpacity={0.32}
              strokeWidth={1}
            />
          );
        })}

        {areaD ? (
          <path
            d={areaD}
            fill={`url(#${areaGradId})`}
            style={{
              opacity: dash.ready ? 1 : 0,
              transition: `opacity 280ms cubic-bezier(0.33, 1, 0.68, 1)`,
            }}
          />
        ) : null}

        {lineD ? (
          <>
            <path
              ref={glowRef}
              d={lineD}
              fill="none"
              stroke={CHART_LINE}
              strokeWidth={LINE_STROKE + 2}
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity={0.07}
            />
            <path
              ref={lineRef}
              d={lineD}
              fill="none"
              stroke={CHART_LINE}
              strokeWidth={LINE_STROKE}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </>
        ) : null}

        {activePoint ? (
          <line
            x1={activePoint.x}
            x2={activePoint.x}
            y1={padT}
            y2={bottomY}
            stroke="#D1D5DB"
            strokeWidth={0.85}
            strokeDasharray="3 5"
            opacity={0.55}
            style={{ pointerEvents: "none" }}
          />
        ) : null}

        {points.map((p, i) => {
          const isActive = activeIndex === i;
          const dimmed = activeIndex !== null && !isActive;
          const r = isActive ? 6.75 : 4;
          return (
            <g key={`ptg-${series[i]?.dayKey ?? i}`} style={{ pointerEvents: "none" }}>
              {isActive ? (
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={12}
                  fill={CHART_LINE}
                  fillOpacity={0.1}
                  stroke={CHART_LINE}
                  strokeOpacity={0.22}
                  strokeWidth={1}
                />
              ) : null}
              <circle
                cx={p.x}
                cy={p.y}
                r={r}
                fill="#ffffff"
                stroke={CHART_LINE}
                strokeWidth={isActive ? 2.75 : 2}
                opacity={dimmed ? 0.22 : dash.ready ? 1 : 0}
                style={{
                  transition: `opacity ${ANIM_MS}ms ease, r 150ms cubic-bezier(0.33, 1, 0.68, 1), stroke-width 150ms ease`,
                }}
              />
            </g>
          );
        })}

        {points.map((p, i) => {
          if (i % labelSkip !== 0 && i !== n - 1 && i !== 0) {
            return null;
          }
          const isActive = activeIndex === i;
          return (
            <text
              key={`x-${series[i]?.dayKey ?? i}`}
              x={p.x}
              y={h - 10}
              textAnchor={i === 0 ? "start" : i === points.length - 1 ? "end" : "middle"}
              style={{
                fontSize: n > 18 ? "9.5px" : "11px",
                fontWeight: isActive ? 700 : 600,
                fontFamily: "inherit",
                letterSpacing: "0.01em",
                fill: isActive ? "#1f2937" : "#6b7280",
                pointerEvents: "none",
              }}
            >
              {p.label}
            </text>
          );
        })}

        {yTicks.map(({ t: tickT, label }) => {
          const y = padT + innerH * (1 - tickT);
          return (
            <text
              key={`y-${tickT}`}
              x={yAxisTickX}
              y={y + 3.5}
              style={{
                fontSize: "10.5px",
                fontWeight: 600,
                fontFamily: "inherit",
                fontVariantNumeric: "tabular-nums",
                fill: "#6b7280",
                pointerEvents: "none",
              }}
            >
              {label}
            </text>
          );
        })}

        <rect
          x={padL - 2}
          y={padT - 4}
          width={innerW + 4}
          height={innerH + padB + 8}
          fill="transparent"
          style={{ cursor: "crosshair", touchAction: "none" }}
          onPointerMove={(e) => {
            if (e.currentTarget.ownerSVGElement) {
              handleOverlayPointer(e.clientX, e.currentTarget.ownerSVGElement);
            }
          }}
          onPointerDown={(e) => {
            if (e.currentTarget.ownerSVGElement) {
              handleOverlayPointer(e.clientX, e.currentTarget.ownerSVGElement);
            }
          }}
        />
      </svg>

      {activePoint && activeDayKey ? (
        <div
          className="pointer-events-none absolute z-10 max-w-[min(260px,calc(100%-0.75rem))] rounded-lg border border-zinc-200 bg-[#FFFFFF]/98 px-2.5 py-2 text-left shadow-sm backdrop-blur-[2px] motion-safe:transition-[opacity,left,transform] motion-safe:duration-[150ms] motion-safe:ease-out"
          style={{
            left: `${tooltipXPct}%`,
            top: 8,
            transform: tooltipTransform,
          }}
        >
          <p className="text-[12.5px] font-semibold leading-snug text-zinc-900">{formatTooltipDate(activeDayKey)}</p>
          <p className="mt-2 text-[12px] font-medium leading-snug text-zinc-600">
            {activePoint.count === 1
              ? t("dashboard.operational.chart.tooltip_day_requests_one")
              : t("dashboard.operational.chart.tooltip_day_requests", { count: activePoint.count })}
          </p>
        </div>
      ) : null}

      {dash.ready && sumCounts === 0 ? (
        <p className="type-body-secondary pointer-events-none absolute bottom-2 left-1/2 w-[min(100%,20rem)] -translate-x-1/2 text-center text-[12px] leading-snug text-zinc-500">
          {t("dashboard.operational.chart.empty_hint")}
        </p>
      ) : null}

      {dash.ready ? (
        <IntakeChartInsights series={series} dayRange={dayRange} chartSummary={chartSummary} />
      ) : null}
    </div>
  );
}

type StatusStackedBarProps = {
  items: [string, number][];
};

/**
 * Dominant pipeline status as a single horizontal bar (share of total) + label "Status — N%".
 * `items` must be sorted by count descending (see dashboard page).
 */
export function StatusStackedBar({ items }: StatusStackedBarProps) {
  const sum = items.reduce((s, [, c]) => s + c, 0);
  if (items.length === 0 || sum === 0) {
    return null;
  }

  const [topStatus, topCount] = items[0];
  const pct = Math.max(0, Math.min(100, Math.round((topCount / sum) * 100)));

  return (
    <div className="w-full min-w-0" role="img" aria-label={t("dashboard.charts.status_distribution_aria")}>
      <p className="text-[12px] font-semibold leading-tight tracking-[-0.01em] text-zinc-900">
        <span>{tStatus(topStatus)}</span>
        <span className="font-medium text-zinc-400"> — </span>
        <span className="tabular-nums text-zinc-600">{pct}%</span>
      </p>
      <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-zinc-100">
        <div
          className="motion-interactive h-full rounded-full bg-[#4A7C59]"
          style={{ width: `${pct}%` }}
          title={`${tStatus(topStatus)} ${pct}%`}
        />
      </div>
    </div>
  );
}
