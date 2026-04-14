import { statusData } from '../../data/mockData';

interface DonutSegment {
  value: number;
  color: string;
  darkColor: string;
  label: string;
}

const segments: DonutSegment[] = [
  { value: statusData.akkoord, color: '#15803d', darkColor: '#4ade80', label: 'Akkoord' },
  { value: statusData.open, color: '#1d4ed8', darkColor: '#60a5fa', label: 'Open' },
  { value: statusData.verloren, color: '#b91c1c', darkColor: '#f87171', label: 'Verloren' },
];

const R = 52;
const CX = 70;
const CY = 70;
const STROKE = 10;

function polarToXY(cx: number, cy: number, r: number, angle: number) {
  const rad = (angle - 90) * (Math.PI / 180);
  return {
    x: cx + r * Math.cos(rad),
    y: cy + r * Math.sin(rad),
  };
}

function arcPath(cx: number, cy: number, r: number, startAngle: number, endAngle: number) {
  const start = polarToXY(cx, cy, r, startAngle);
  const end = polarToXY(cx, cy, r, endAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`;
}

export function StatusDonut() {
  const total = segments.reduce((s, seg) => s + seg.value, 0) || 1;
  let currentAngle = 0;

  const arcs = segments.map(seg => {
    const pct = seg.value / total;
    const sweep = pct * 360;
    const start = currentAngle;
    const end = currentAngle + sweep - (sweep > 2 ? 1 : 0);
    currentAngle += sweep;
    return { ...seg, path: sweep > 0 ? arcPath(CX, CY, R, start, end) : null };
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <p className="text-[10px] font-semibold text-neutral-400 dark:text-white/25 uppercase tracking-[0.12em]">Statusverdeling</p>
        <p className="text-[11px] font-semibold text-neutral-700 dark:text-white/35">{total} offertes</p>
      </div>

      <div className="flex flex-col items-center gap-3">
        <div className="relative shrink-0">
          <svg width="100" height="100" viewBox="0 0 140 140">
            <circle
              cx={CX}
              cy={CY}
              r={R}
              fill="none"
              stroke="currentColor"
              strokeWidth={STROKE}
              className="text-slate-100 dark:text-white/[0.06]"
            />
            {arcs.map((arc, i) =>
              arc.path ? (
                <path
                  key={i}
                  d={arc.path}
                  fill="none"
                  stroke={arc.color}
                  strokeWidth={STROKE}
                  strokeLinecap="butt"
                  className="dark:hidden"
                />
              ) : null
            )}
            {arcs.map((arc, i) =>
              arc.path ? (
                <path
                  key={`dark-${i}`}
                  d={arc.path}
                  fill="none"
                  stroke={arc.darkColor}
                  strokeWidth={STROKE}
                  strokeLinecap="butt"
                  className="hidden dark:block"
                />
              ) : null
            )}
            <text
              x={CX}
              y={CY - 5}
              textAnchor="middle"
              fontSize="22"
              fontWeight="700"
              fill="currentColor"
              className="fill-slate-800 dark:fill-white/80"
            >
              {total}
            </text>
            <text
              x={CX}
              y={CY + 12}
              textAnchor="middle"
              fontSize="10"
              fill="currentColor"
              className="fill-slate-400 dark:fill-white/25"
            >
              totaal
            </text>
          </svg>
        </div>

        <div className="flex flex-col w-full min-w-0">
          {segments.map((seg, i) => (
            <div key={i} className="flex items-center justify-between gap-3 py-1.5 border-b border-slate-100 dark:border-white/[0.05] last:border-0">
              <div className="flex items-center gap-2">
                <span
                  className="w-1.5 h-1.5 rounded-sm shrink-0"
                  style={{ backgroundColor: seg.color }}
                />
                <span className="text-[11px] font-normal text-slate-500 dark:text-white/40">
                  {seg.label}
                </span>
              </div>
              <span className="text-[13px] font-bold text-slate-900 dark:text-white/80 tabular-nums">
                {seg.value}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
