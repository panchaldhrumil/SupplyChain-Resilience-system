// Riskometer — SVG arc gauge showing highest-risk corridor score (0-100)
// Three distinct states:
//   1. No corridors loaded         → "Awaiting pipeline data" (no gauge)
//   2. Corridors loaded, top = 0   → "All corridors nominal" (gauge at zero, green)
//   3. Corridors loaded, score > 0 → Full gauge with score + level
import { CORRIDOR_LABELS, LEVEL_COLORS } from '../utils/corridors';

const SIZE   = 200;
const CX     = SIZE / 2;
const CY     = SIZE / 2 + 10;
const R      = 76;
const STROKE = 13;

const START_DEG = -210;
const SWEEP_DEG = 240;

function polarToXY(deg, r = R) {
  const rad = (deg * Math.PI) / 180;
  return [CX + r * Math.cos(rad), CY + r * Math.sin(rad)];
}

function describeArc(startDeg, endDeg, r = R) {
  const [sx, sy] = polarToXY(startDeg, r);
  const [ex, ey] = polarToXY(endDeg,   r);
  const large = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${sx} ${sy} A ${r} ${r} 0 ${large} 1 ${ex} ${ey}`;
}

function NoDataState() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '24px 0' }}>
      <div style={{ fontSize: 32 }}>📡</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: '#475569', textAlign: 'center' }}>
        Awaiting pipeline data
      </div>
      <div style={{ fontSize: 11, color: '#334155', textAlign: 'center', maxWidth: 160, lineHeight: 1.5 }}>
        Run <code style={{ color: '#7dd3fc' }}>live_macro_pipeline.py</code> to populate corridor scores
      </div>
    </div>
  );
}

export default function Riskometer({ corridors = [], scoredAt }) {
  // ── State 1: No data loaded yet
  if (!corridors.length) {
    return <NoDataState />;
  }

  // Find highest scoring corridor
  const top    = corridors.reduce((a, b) => (b.score > a.score ? b : a));
  const score  = top.score ?? 0;
  const level  = top.level ?? 'green';
  const label  = CORRIDOR_LABELS[top.corridor] || top.corridor;
  const colors = LEVEL_COLORS[level];
  const totalEvents = corridors.reduce((s, c) => s + (c.articles_in_window || 0), 0);

  const valueDeg = START_DEG + (score / 100) * SWEEP_DEG;
  const trackPath   = describeArc(START_DEG, START_DEG + SWEEP_DEG);
  const filledPath  = score > 0 ? describeArc(START_DEG, valueDeg) : null;
  const [ndlX, ndlY] = polarToXY(valueDeg, R - 4);

  const tick33 = polarToXY(START_DEG + (33 / 100) * SWEEP_DEG, R + 10);
  const tick66 = polarToXY(START_DEG + (66 / 100) * SWEEP_DEG, R + 10);

  // ── State 2: All corridors nominal (score = 0 but data exists)
  const isNominal = score === 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
      <svg width={SIZE} height={SIZE * 0.78} viewBox={`0 0 ${SIZE} ${SIZE * 0.78}`}>
        <defs>
          <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"   stopColor="#22c55e" />
            <stop offset="33%"  stopColor="#f59e0b" />
            <stop offset="100%" stopColor="#ef4444" />
          </linearGradient>
        </defs>

        {/* Track */}
        <path d={trackPath} fill="none" stroke="#1f2d45" strokeWidth={STROKE} strokeLinecap="round" />

        {/* Filled value arc */}
        {filledPath && (
          <path
            d={filledPath}
            fill="none"
            stroke={colors.ring}
            strokeWidth={STROKE}
            strokeLinecap="round"
            style={{ filter: `drop-shadow(0 0 6px ${colors.ring}88)` }}
          />
        )}

        {/* Zone dividers */}
        {[tick33, tick66].map(([tx, ty], i) => (
          <circle key={i} cx={tx} cy={ty} r={2.5} fill="#374151" />
        ))}

        {/* Needle dot */}
        <circle cx={ndlX} cy={ndlY} r={5} fill={colors.ring}
          style={{ filter: `drop-shadow(0 0 4px ${colors.ring})` }} />

        {/* Score */}
        <text x={CX} y={CY - 4} textAnchor="middle" fontSize={32} fontWeight={700}
          fill={isNominal ? '#22c55e' : colors.ring} fontFamily="Inter, sans-serif">
          {score.toFixed(0)}
        </text>
        <text x={CX} y={CY + 16} textAnchor="middle" fontSize={10} fill="#64748b"
          fontFamily="Inter, sans-serif" letterSpacing="0.08em">
          RISK SCORE
        </text>
      </svg>

      {/* Corridor label + badge */}
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 3 }}>
          {isNominal ? 'All corridors nominal' : 'Highest risk corridor'}
        </div>
        <div style={{ fontSize: 13, fontWeight: 600, color: colors.text, marginBottom: 4 }}>
          {isNominal ? '✓ No elevated risk signals' : label}
        </div>
        <span className={`badge badge-${level}`}>
          {LEVEL_COLORS[level]?.label || level.toUpperCase()}
        </span>
      </div>

      {/* Data provenance caption */}
      <div style={{ fontSize: 10, color: '#334155', textAlign: 'center', marginTop: 4, lineHeight: 1.5 }}>
        {totalEvents} events · 36h decay · 7-day window
        {scoredAt && (
          <><br />Scored {new Date(scoredAt).toLocaleTimeString()}</>
        )}
        {isNominal && score === 0 && (
          <><br /><span style={{ color: '#22c55e' }}>✓ Verified calm — data present, no elevated signals</span></>
        )}
      </div>
    </div>
  );
}
