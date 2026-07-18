// BufferStack — horizontal stacked bar showing on_water / refinery_stock / SPR days
// Three distinct states per layer:
//   1. Loading  — data hasn't arrived yet from API
//   2. Pending  — data arrived but value is null (needs manual config — on_water only)
//   3. Known    — real cited value available
import { useState } from 'react';

const LAYER_COLORS = {
  on_water:       { fill: '#3b82f6', light: '#93c5fd', label: 'Crude on Water' },
  refinery_stock: { fill: '#14b8a6', light: '#5eead4', label: 'Refinery Stock' },
  spr:            { fill: '#8b5cf6', light: '#c4b5fd', label: 'SPR' },
};
const DEFAULT_COLOR = { fill: '#475569', light: '#94a3b8', label: 'Other' };

function LayerSegment({ layer, days, totalDays, color, onClick, active }) {
  const pct = totalDays > 0 ? (days / totalDays) * 100 : 0;
  return (
    <div
      style={{
        width: `${Math.max(pct, pct > 0 ? 1.5 : 0)}%`,
        background: active ? color.light : color.fill,
        borderRadius: 0,
        cursor: 'pointer',
        transition: 'background 0.2s, filter 0.2s',
        filter: active ? `drop-shadow(0 0 6px ${color.light})` : 'none',
        position: 'relative',
      }}
      onClick={onClick}
      title={`${color.label}: ${days?.toFixed(1) ?? '—'} days`}
    />
  );
}

function PendingBadge({ note }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '5px 10px', borderRadius: 6,
      background: 'rgba(245,158,11,0.08)',
      border: '1px solid rgba(245,158,11,0.25)',
    }}>
      <span style={{ fontSize: 12 }}>⚠</span>
      <span style={{ fontSize: 11, color: '#f59e0b', lineHeight: 1.4 }}>
        {note || 'Pending config — fill import_mix.json with PPAC data'}
      </span>
    </div>
  );
}

export default function BufferStack({ data, loading }) {
  const [activeLayer, setActiveLayer] = useState(null);

  // ── State 1: First load spinner (brief)
  if (loading && !data) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#475569', fontSize: 12, padding: '24px 0' }}>
        <div style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid #1f2d45', borderTopColor: '#3b82f6', animation: 'spin 0.8s linear infinite' }} />
        Loading buffer data…
      </div>
    );
  }

  // ── State 2: API error / no data returned
  if (!data?.layers?.length) {
    return (
      <div style={{ color: '#475569', fontSize: 12, padding: '16px 0', textAlign: 'center' }}>
        <div style={{ fontSize: 20, marginBottom: 6 }}>📊</div>
        No buffer data — ensure <code>buffer_config.json</code> is present and the API is running.
      </div>
    );
  }

  const layers    = data.layers;
  // For the bar, use 0 for null (pending) layers — they show as invisible segment
  const knownDays = layers.reduce((sum, l) => sum + (l.days_cover ?? 0), 0);
  const totalDays = data.total_days_cover || knownDays;

  const onWaterLayer = layers.find(l => l.layer === 'on_water');
  const knownLayers  = layers.filter(l => l.layer !== 'on_water' || l.days_cover != null);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

      {/* Stacked bar — only known layers contribute width */}
      <div style={{
        display: 'flex', height: 28, borderRadius: 6, overflow: 'hidden',
        border: '1px solid var(--border)', background: 'var(--bg-base)',
      }}>
        {layers.map(lay => {
          const days  = lay.days_cover ?? 0;
          const color = LAYER_COLORS[lay.layer] || DEFAULT_COLOR;
          return (
            <LayerSegment
              key={lay.layer}
              layer={lay.layer}
              days={days}
              totalDays={totalDays}
              color={color}
              active={activeLayer === lay.layer}
              onClick={() => setActiveLayer(activeLayer === lay.layer ? null : lay.layer)}
            />
          );
        })}
      </div>

      {/* Total — only counts known layers */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Verified buffer total
        </span>
        <span style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
          {knownDays.toFixed(1)}{' '}
          <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--text-muted)' }}>days</span>
        </span>
      </div>

      {/* Legend + detail rows */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {layers.map(lay => {
          const color    = LAYER_COLORS[lay.layer] || DEFAULT_COLOR;
          const isActive = activeLayer === lay.layer;
          const isPending = lay.days_cover == null;

          return (
            <div
              key={lay.layer}
              onClick={() => setActiveLayer(isActive ? null : lay.layer)}
              style={{
                display: 'grid', gridTemplateColumns: '12px 1fr auto',
                alignItems: 'start', gap: '0 8px', cursor: 'pointer',
                padding: '6px 8px', borderRadius: 6,
                background: isActive ? 'rgba(255,255,255,0.04)' : 'transparent',
                border: `1px solid ${isActive ? color.fill + '60' : 'transparent'}`,
                transition: 'background 0.15s, border-color 0.15s',
              }}
            >
              <div style={{ width: 12, height: 12, borderRadius: 3, background: color.fill, marginTop: 2 }} />
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{lay.label}</div>
                {isActive && (
                  <div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                    {lay.methodology === 'estimated'
                      ? <span style={{ color: '#f59e0b' }}>⚠ Estimated — {lay.note || 'not a published figure'}</span>
                      : <span style={{ color: '#22c55e' }}>✓ {lay.display_badge}</span>
                    }
                    <br />
                    <span title={lay.source_url}>
                      Source: {lay.source || '—'}
                      {lay.last_verified && <> · Verified {lay.last_verified}</>}
                    </span>
                  </div>
                )}
              </div>
              <div style={{ textAlign: 'right' }}>
                {isPending
                  ? <span style={{ fontSize: 10, color: '#f59e0b', fontWeight: 700, letterSpacing: '0.04em' }}>PENDING</span>
                  : <span style={{ fontSize: 14, fontWeight: 700, color: color.light, fontVariantNumeric: 'tabular-nums' }}>
                      {lay.days_cover.toFixed(1)}d
                    </span>
                }
                {lay.methodology === 'estimated' && lay.days_cover != null && (
                  <div style={{ fontSize: 9, color: '#f59e0b', letterSpacing: '0.04em' }}>EST.</div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* on_water pending notice — shown only when null */}
      {onWaterLayer && onWaterLayer.days_cover == null && (
        <PendingBadge note="on_water: fill import_share_pct in backend/config/import_mix.json (PPAC data)" />
      )}

      {/* Derived vessel traffic info */}
      {data.vessels_in_transit && data.vessels_in_transit.estimated_vessels != null && (
        <div style={{
          marginTop: 8,
          background: 'var(--bg-code)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          padding: '10px 12px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-primary)' }}>
              🚢 Crude Tankers on Water
            </span>
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '0.05em',
              background: 'rgba(245,158,11,0.12)', color: '#f59e0b',
              padding: '1px 5px', borderRadius: 3, border: '1px solid rgba(245,158,11,0.2)',
            }}>
              {data.vessels_in_transit.display_badge}
            </span>
          </div>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#3b82f6', marginBottom: 4 }}>
            {data.vessels_in_transit.estimated_vessels}{' '}
            <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--text-muted)' }}>VLCC/Suezmax equivalents</span>
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-footer)', lineHeight: 1.4 }}>
            {data.vessels_in_transit.note}
          </div>
        </div>
      )}

      <div style={{ fontSize: 10, color: 'var(--text-footer)', marginTop: 2 }}>
        Click a layer to see source citation · {data.note}
      </div>
    </div>
  );
}

