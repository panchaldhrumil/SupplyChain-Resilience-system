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

      {/* ── Item 3 & 5: Detailed Breakdown Tables (Refineries & SPR) ── */}
      {(data.refinery_breakdown || data.spr_breakdown) && (
        <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
            <button
              onClick={() => setActiveLayer(activeLayer === 'refinery_detail' ? null : 'refinery_detail')}
              style={{
                flex: '1 1 140px', padding: '6px 8px', fontSize: 10, fontWeight: 700,
                borderRadius: 6, cursor: 'pointer', border: '1px solid var(--border)',
                background: activeLayer === 'refinery_detail' ? 'rgba(20,184,166,0.15)' : 'var(--bg-card)',
                color: activeLayer === 'refinery_detail' ? '#5eead4' : 'var(--text-primary)',
                textAlign: 'center', whiteSpace: 'nowrap',
              }}
            >
              🏭 Refinery Stock Breakdown ({data.refinery_breakdown?.refineries?.length || 0})
            </button>
            <button
              onClick={() => setActiveLayer(activeLayer === 'spr_detail' ? null : 'spr_detail')}
              style={{
                flex: '1 1 140px', padding: '6px 8px', fontSize: 10, fontWeight: 700,
                borderRadius: 6, cursor: 'pointer', border: '1px solid var(--border)',
                background: activeLayer === 'spr_detail' ? 'rgba(139,92,246,0.15)' : 'var(--bg-card)',
                color: activeLayer === 'spr_detail' ? '#c4b5fd' : 'var(--text-primary)',
                textAlign: 'center', whiteSpace: 'nowrap',
              }}
            >
              🛢️ SPR Site Breakdown (3)
            </button>
          </div>

          {/* Refinery Breakdown Table */}
          {activeLayer === 'refinery_detail' && data.refinery_breakdown && (
            <div style={{
              background: 'var(--bg-card)', border: '1px solid var(--border)',
              borderRadius: 8, padding: 12, fontSize: 11,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, alignItems: 'baseline' }}>
                <span style={{ fontWeight: 700, color: '#14b8a6' }}>
                  Refinery Product Stock Allocation ({data.refinery_breakdown.aggregate_stock_days} Days Total Aggregate)
                </span>
                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                  {data.refinery_breakdown.coverage_pct}% Capacity Mapped
                </span>
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 10, lineHeight: 1.4 }}>
                {data.refinery_breakdown.methodology_note}
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 11 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', fontSize: 10 }}>
                      <th style={{ padding: '4px 6px' }}>REFINERY</th>
                      <th style={{ padding: '4px 6px' }}>OPERATOR</th>
                      <th style={{ padding: '4px 6px', textAlign: 'right' }}>CAPACITY</th>
                      <th style={{ padding: '4px 6px', textAlign: 'right' }}>SHARE</th>
                      <th style={{ padding: '4px 6px', textAlign: 'right' }}>EST. STOCK</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.refinery_breakdown.refineries.map((r, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', color: 'var(--text-primary)' }}>
                        <td style={{ padding: '5px 6px', fontWeight: r.name.startsWith('Others') ? 400 : 600 }}>{r.name}</td>
                        <td style={{ padding: '5px 6px', color: 'var(--text-muted)', fontSize: 10 }}>{r.operator}</td>
                        <td style={{ padding: '5px 6px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{r.capacity_mmtpa} MMTPA</td>
                        <td style={{ padding: '5px 6px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{r.share_pct}%</td>
                        <td style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 700, color: '#5eead4', fontVariantNumeric: 'tabular-nums' }}>
                          {r.stock_days_est}d
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ fontSize: 9, color: 'var(--text-footer)', marginTop: 8 }}>
                Source: {data.refinery_breakdown.source} · Aggregate: {data.refinery_breakdown.aggregate_source}
              </div>
            </div>
          )}

          {/* SPR Site Breakdown Table */}
          {activeLayer === 'spr_detail' && data.spr_breakdown && (
            <div style={{
              background: 'var(--bg-card)', border: '1px solid var(--border)',
              borderRadius: 8, padding: 12, fontSize: 11,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, alignItems: 'baseline' }}>
                <span style={{ fontWeight: 700, color: '#8b5cf6' }}>
                  Strategic Petroleum Reserve (SPR) Site Fill
                </span>
                <span style={{ fontSize: 10, color: '#c4b5fd', fontWeight: 600 }}>
                  {data.spr_breakdown.national_fill_pct}% National Fill Rate
                </span>
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 10, lineHeight: 1.4 }}>
                {data.spr_breakdown.methodology_note}
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 11 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', fontSize: 10 }}>
                      <th style={{ padding: '4px 6px' }}>ISPRL LOCATION</th>
                      <th style={{ padding: '4px 6px', textAlign: 'right' }}>CAPACITY</th>
                      <th style={{ padding: '4px 6px', textAlign: 'right' }}>FILL RATE</th>
                      <th style={{ padding: '4px 6px', textAlign: 'right' }}>EST. CRUDE HELD</th>
                      <th style={{ padding: '4px 6px', textAlign: 'right' }}>EST. DAYS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.spr_breakdown.sites.map((s, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', color: 'var(--text-primary)' }}>
                        <td style={{ padding: '5px 6px', fontWeight: 600 }}>{s.site}</td>
                        <td style={{ padding: '5px 6px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{s.capacity_mmt} MMT</td>
                        <td style={{ padding: '5px 6px', textAlign: 'right', color: '#c4b5fd', fontVariantNumeric: 'tabular-nums' }}>{s.fill_pct_national}%</td>
                        <td style={{ padding: '5px 6px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{s.est_fill_mmt} MMT</td>
                        <td style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 700, color: '#c4b5fd', fontVariantNumeric: 'tabular-nums' }}>
                          {s.est_days_cover}d
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ fontSize: 9, color: 'var(--text-footer)', marginTop: 8 }}>
                Source: {data.spr_breakdown.source} · Verified: {data.spr_breakdown.last_verified}
              </div>
            </div>
          )}
        </div>
      )}

      <div style={{ fontSize: 10, color: 'var(--text-footer)', marginTop: 2 }}>
        Click a layer to see source citation · {data.note}
      </div>
    </div>
  );
}


