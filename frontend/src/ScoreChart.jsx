// Danger score over time. Click anywhere to jump the video to that moment.
export default function ScoreChart({ series, threshold, triggers = [], onSeek }) {
  if (!series?.length) return null;
  const W = 720, H = 220, P = { l: 34, r: 10, t: 10, b: 26 };
  const tMax = Math.max(series[series.length - 1].time_s, 0.1);
  const x = (t) => P.l + (t / tMax) * (W - P.l - P.r);
  const y = (v) => P.t + (1 - Math.min(Math.max(v, 0), 1)) * (H - P.t - P.b);
  const path = (f) =>
    series.map((d, i) => `${i ? "L" : "M"}${x(d.time_s).toFixed(1)},${y(f(d)).toFixed(1)}`).join("");
  const area = `${path((d) => d.score)}L${x(tMax)},${y(0)}L${x(0)},${y(0)}Z`;
  const xTicks = Array.from({ length: 6 }, (_, i) => (tMax * i) / 5);

  const click = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    const f = Math.min(Math.max((px - P.l) / (W - P.l - P.r), 0), 1);
    onSeek?.(f * tMax);
  };

  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} onClick={click} role="img"
         aria-label="Danger score over video time">
      {[0, 0.5, 1].map((v) => (
        <g key={v}>
          <line x1={P.l} x2={W - P.r} y1={y(v)} y2={y(v)} className="grid" />
          <text x={P.l - 6} y={y(v) + 4} textAnchor="end" className="tick">{v}</text>
        </g>
      ))}
      {xTicks.map((t) => (
        <text key={t} x={x(t)} y={H - 8} textAnchor="middle" className="tick">{t.toFixed(0)}s</text>
      ))}
      <path d={area} className="area" />
      <path d={path((d) => d.brightness / 255)} className="bright" />
      <path d={path((d) => d.score)} className="score" />
      <line x1={P.l} x2={W - P.r} y1={y(threshold)} y2={y(threshold)} className="thr" />
      {triggers.map((t, i) => (
        <g key={i}>
          <line x1={x(t)} x2={x(t)} y1={P.t} y2={H - P.b} className="trigger" />
          <circle cx={x(t)} cy={P.t + 4} r="4" className="trigger-dot" />
        </g>
      ))}
    </svg>
  );
}
