// CorridorRiskBar — horizontal list of all corridors with mini score bars
import { CORRIDOR_LABELS, LEVEL_COLORS } from '../utils/corridors';

const TREND_META = {
  rising:  { label: '↗ rising', color: '#22c55e' },
  falling: { label: '↘ falling', color: '#f59e0b' },
  stable:  { label: '→ stable', color: '#64748b' },
};

export default function CorridorRiskBar({ corridors = [] }) {
  if (!corridors.length) {
    return <div style={{ color: '#475569', fontSize: 12 }}>Awaiting corridor data…</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {corridors.map(c => {
        const label  = CORRIDOR_LABELS[c.corridor] || c.corridor;
        const colors = LEVEL_COLORS[c.level] || LEVEL_COLORS.green;
        const trendMeta = TREND_META[c.trend] || TREND_META.stable;

        return (
          <div key={c.corridor} style={{ display: 'grid', gridTemplateColumns: '140px 1fr 56px 70px', alignItems: 'center', gap: 8 }}>
            {/* Label */}
            <div style={{ fontSize: 11, color: '#94a3b8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {label}
            </div>

            {/* Bar track */}
            <div style={{ height: 6, background: '#1f2d45', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width:  `${c.score}%`,
                background: colors.ring,
                borderRadius: 3,
                transition: 'width 0.6s ease',
                boxShadow: c.level !== 'green' ? `0 0 6px ${colors.ring}88` : 'none',
              }} />
            </div>

            {/* Score */}
            <div style={{ fontSize: 11, fontWeight: 700, color: colors.text, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
              {c.score.toFixed(0)}
            </div>

            {/* Trend */}
            <div style={{ fontSize: 10, color: trendMeta.color, textAlign: 'left', whiteSpace: 'nowrap' }}>
              {trendMeta.label}
            </div>
          </div>
        );
      })}
    </div>
  );
}
