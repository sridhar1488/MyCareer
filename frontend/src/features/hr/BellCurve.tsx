import type { components } from '../../api/schema';

type ScorePoint = components['schemas']['ScorePoint'];
type ScoreDistribution = components['schemas']['ScoreDistribution'];

type Dot = ScorePoint & { x: number; y: number };

const width = 960;
const left = 62;
const right = 24;
const plotTop = 28;
const plotBottom = 220;
const plotHeight = plotBottom - plotTop;

function xFor(score: number) {
  return left + ((score - 1) / 4) * (width - left - right);
}

export function BellCurve({ points, distribution }: { points: ScorePoint[]; distribution: ScoreDistribution | null }) {
  const validPoints = points
    .map(point => ({ ...point, value: Number(point.score) }))
    .filter(point => Number.isFinite(point.value) && point.value >= 1 && point.value <= 5);

  if (!distribution || !validPoints.length) {
    return <section className="analytics-chart bell-curve-panel" aria-labelledby="bell-curve-heading">
      <h3 id="bell-curve-heading">Score distribution</h3>
      <p className="muted">The distribution will appear when this cycle has HR-approved evaluations.</p>
    </section>;
  }

  const { bin_counts: bins, reference_counts: reference, mean, maximum } = distribution;
  const curve = reference.map((count, index) => {
    const x = xFor(1 + index * 0.05);
    const y = plotBottom - (count / maximum) * plotHeight;
    return `${index === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(' ');
  const maxLane = Math.max(...Array.from(validPoints.reduce((counts, point) => {
    const key = point.value.toFixed(1);
    counts.set(key, (counts.get(key) ?? 0) + 1);
    return counts;
  }, new Map<string, number>()).values()));
  const axisY = 246 + maxLane * 7;
  const chartHeight = axisY + 58;
  const lanes = new Map<string, number>();
  const dots: Dot[] = [...validPoints]
    .sort((a, b) => a.value - b.value || a.employee_name.localeCompare(b.employee_name))
    .map(point => {
      const key = point.value.toFixed(1);
      const lane = lanes.get(key) ?? 0;
      lanes.set(key, lane + 1);
      return { ...point, x: xFor(point.value), y: 238 + lane * 7 };
    });

  const approvalBins = bins.map((count, index) => {
    const start = 1 + index * 0.5;
    const end = start + 0.5;
    const x = xFor(start) + 1;
    const barWidth = xFor(end) - xFor(start) - 2;
    const barHeight = (count / maximum) * plotHeight;
    return { x, y: plotBottom - barHeight, width: barWidth, height: barHeight, count, start, end };
  });
  const tickValues = Array.from({ length: 5 }, (_, index) => (maximum * index) / 4);

  return <section className="analytics-chart bell-curve-panel" aria-labelledby="bell-curve-heading">
    <div className="section-heading bell-curve-heading">
      <div><h3 id="bell-curve-heading">Employee score distribution</h3><p className="muted">HR-approved final scores on the 1–5 scale for the selected cycle.</p></div>
      <span className="bell-curve-count">{validPoints.length} {validPoints.length === 1 ? 'employee' : 'employees'}</span>
    </div>
    <div className="bell-curve-legend"><span><i className="legend-histogram" />Observed score counts</span><span><i className="legend-normal" />Bell curve reference</span><span><i className="legend-employee" />Individual employee score</span></div>
    <div className="bell-curve-scroll">
      <svg className="bell-curve-svg" viewBox={`0 0 ${width} ${chartHeight}`} role="img" aria-labelledby="bell-curve-title bell-curve-desc">
        <title id="bell-curve-title">Distribution of HR-approved employee scores</title>
        <desc id="bell-curve-desc">Histogram and fitted bell curve of {validPoints.length} final scores. Individual dots show employee scores along a horizontal scale from one to five. Average score is {mean.toFixed(1)}.</desc>
        {tickValues.map((value, index) => {
          const y = plotBottom - (index / 4) * plotHeight;
          return <g key={index}><line x1={left} x2={width - right} y1={y} y2={y} className="bell-gridline"/><text x={left - 12} y={y + 4} className="bell-axis-label" textAnchor="end">{Math.round(value)}</text></g>;
        })}
        {approvalBins.map(bin => <g key={bin.start}>
          <rect x={bin.x} y={bin.y} width={bin.width} height={Math.max(0, bin.height)} rx="4" className="bell-histogram-bar"><title>{bin.start.toFixed(1)}–{bin.end.toFixed(1)}: {bin.count} employees</title></rect>
        </g>)}
        <path d={curve} className="bell-normal-curve" />
        <line x1={left} x2={width - right} y1={plotBottom} y2={plotBottom} className="bell-axis-line" />
        {dots.map((dot, index) => <circle key={`${dot.employee_id}-${index}`} cx={dot.x} cy={dot.y} r="4" className="bell-employee-dot"><title>{dot.employee_name} · {dot.employee_id} · score {dot.score} / 5</title></circle>)}
        <line x1={left} x2={width - right} y1={axisY} y2={axisY} className="bell-axis-line" />
        {[1, 2, 3, 4, 5].map(score => <g key={score}><line x1={xFor(score)} x2={xFor(score)} y1={axisY - 4} y2={axisY + 4} className="bell-axis-line"/><text x={xFor(score)} y={axisY + 22} className="bell-axis-label" textAnchor="middle">{score}</text></g>)}
        <text x={(left + width - right) / 2} y={axisY + 46} className="bell-axis-title" textAnchor="middle">Final score / 5</text>
        <text x="15" y={(plotTop + plotBottom) / 2} className="bell-axis-title" textAnchor="middle" transform={`rotate(-90 15 ${(plotTop + plotBottom) / 2})`}>Employees</text>
      </svg>
    </div>
    <p className="bell-curve-note">Mean score: <strong>{mean.toFixed(1)} / 5</strong>. Each dot represents one employee; hover over a dot to see the employee and score. The curve is a reference fitted to these results and does not impose a rating quota.</p>
  </section>;
}
