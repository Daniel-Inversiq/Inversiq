import { revenueData } from '../../data/mockData';

const CHART_H = 150;
const CHART_W = 460;
const PAD_LEFT = 46;
const PAD_RIGHT = 16;
const PAD_TOP = 14;
const PAD_BOTTOM = 26;

function buildPath(points: { x: number; y: number }[], innerH: number, close = false): string {
  if (points.length === 0) return '';
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 1; i < points.length; i++) {
    const prev = points[i - 1];
    const curr = points[i];
    const cpx = (prev.x + curr.x) / 2;
    d += ` C ${cpx} ${prev.y}, ${cpx} ${curr.y}, ${curr.x} ${curr.y}`;
  }
  if (close) {
    const baseline = PAD_TOP + innerH;
    d += ` L ${points[points.length - 1].x} ${baseline}`;
    d += ` L ${points[0].x} ${baseline} Z`;
  }
  return d;
}

export function RevenueChart() {
  const rawMax = Math.max(...revenueData.map(d => d.value));
  const maxVal = rawMax > 0 ? Math.ceil((rawMax * 1.2) / 100) * 100 : 500;
  const innerW = CHART_W - PAD_LEFT - PAD_RIGHT;
  const innerH = CHART_H - PAD_TOP - PAD_BOTTOM;

  const totalRevenue = revenueData.reduce((s, d) => s + d.value, 0);

  const points = revenueData.map((d, i) => ({
    x: PAD_LEFT + (i / (revenueData.length - 1)) * innerW,
    y: PAD_TOP + innerH - (d.value / maxVal) * innerH,
  }));

  const tickStep = maxVal <= 500 ? 250 : maxVal <= 1000 ? 500 : 1000;
  const yTicks: number[] = [];
  for (let t = 0; t <= maxVal; t += tickStep) yTicks.push(t);

  const areaPath = buildPath(points, innerH, true);
  const linePath = buildPath(points, innerH, false);
  const lastPoint = points[points.length - 1];

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="text-[9px] font-semibold text-neutral-400 dark:text-white/25 uppercase tracking-[0.12em]">Omzet over tijd</p>
        <p className="text-[11px] font-semibold text-neutral-700 dark:text-white/35 tabular-nums">
          € {totalRevenue.toLocaleString('nl-NL')} totaal
        </p>
      </div>

      <div className="w-full overflow-hidden">
        <svg
          viewBox={`0 0 ${CHART_W} ${CHART_H}`}
          className="w-full"
          style={{ height: `${CHART_H}px` }}
          preserveAspectRatio="xMidYMid meet"
        >
          {yTicks.map(tick => {
            const y = PAD_TOP + innerH - (tick / maxVal) * innerH;
            return (
              <g key={tick}>
                <line
                  x1={PAD_LEFT}
                  y1={y}
                  x2={CHART_W - PAD_RIGHT}
                  y2={y}
                  stroke="currentColor"
                  strokeWidth="0.5"
                  strokeDasharray={tick === 0 ? undefined : '3 3'}
                  className="text-neutral-200 dark:text-white/[0.06]"
                />
                <text
                  x={PAD_LEFT - 6}
                  y={y + 4}
                  textAnchor="end"
                  fontSize="9"
                  className="fill-neutral-400 dark:fill-white/25"
                  fill="currentColor"
                >
                  {tick === 0 ? '0' : `€${tick}`}
                </text>
              </g>
            );
          })}

          {revenueData.map((d, i) => {
            const x = PAD_LEFT + (i / (revenueData.length - 1)) * innerW;
            const shortMonth = d.month.replace(' 2025', '').replace(' 2026', '');
            return (
              <text
                key={i}
                x={x}
                y={CHART_H - 6}
                textAnchor="middle"
                fontSize="9"
                className="fill-neutral-400 dark:fill-white/25"
                fill="currentColor"
              >
                {shortMonth}
              </text>
            );
          })}

          <path d={areaPath} fill="rgba(10, 10, 10, 0.06)" />
          <path d={linePath} fill="none" stroke="#0a0a0a" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
          <circle cx={lastPoint.x} cy={lastPoint.y} r="3" fill="#0a0a0a" stroke="white" strokeWidth="1.5" />
        </svg>
      </div>
    </div>
  );
}
