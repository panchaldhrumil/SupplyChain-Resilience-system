// ProcurementEngine.jsx — Module 3 (Procurement Recommendation Engine)
// Dynamic weighted alternatives ranking calling /api/procurement-recommend.
import { useState, useEffect } from 'react';
import { API_BASE } from '../config';

export default function ProcurementEngine() {
  const [disruptedId, setDisruptedId]   = useState('Saudi Arabia');
  const [volumePct, setVolumePct]       = useState(20);
  const [maxTransit, setMaxTransit]     = useState(30);
  const [data, setData]                 = useState(null);
  const [loading, setLoading]           = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const fetchRecommend = async () => {
      setLoading(true);
      try {
        const url = `${API_BASE}/api/procurement-recommend?disrupted_id=${encodeURIComponent(disruptedId)}&required_volume_pct=${volumePct}&max_transit_days=${maxTransit}`;
        const res = await fetch(url, { signal: controller.signal });
        const json = await res.json();
        setData(json);
      } catch (e) {
        if (e.name !== 'AbortError') {
          console.error(e);
        }
      } finally {
        setLoading(false);
      }
    };
    fetchRecommend();
    return () => controller.abort();
  }, [disruptedId, volumePct, maxTransit]);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '350px 1fr', gap: '1.5rem' }}>
      {/* Inputs Panel */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
          Disruption Context
        </div>

        {/* Disrupted Supplier / Corridor */}
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Disrupted Node / Source
          </label>
          <select
            value={disruptedId}
            onChange={e => setDisruptedId(e.target.value)}
            style={{
              width: '100%', background: 'var(--bg-input)', border: '1px solid var(--border-input)',
              color: 'var(--text-primary)', borderRadius: 8, padding: '10px 12px', fontSize: 13,
              cursor: 'pointer',
            }}
          >
            <optgroup label="Primary Shipping Corridors">
              <option value="hormuz">Strait of Hormuz</option>
              <option value="suez">Suez Canal</option>
              <option value="red_sea">Red Sea / Bab-el-Mandeb</option>
              <option value="cape_of_good_hope">Cape of Good Hope</option>
              <option value="russia_route">Russia / Black Sea</option>
              <option value="malacca">Malacca Strait</option>
            </optgroup>
            <optgroup label="Major Supplier Countries">
              <option value="Iraq">Iraq</option>
              <option value="Saudi Arabia">Saudi Arabia</option>
              <option value="Russia">Russia</option>
              <option value="UAE">UAE</option>
              <option value="USA">USA</option>
              <option value="Nigeria">Nigeria</option>
              <option value="Kuwait">Kuwait</option>
            </optgroup>
          </select>
        </div>

        {/* Volume to Replace */}
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Volume to Replace: {volumePct}% of Daily Import
          </label>
          <input
            type="range" min="5" max="100" step="5"
            value={volumePct}
            onChange={e => setVolumePct(parseInt(e.target.value))}
            style={{ width: '100%', accentColor: '#3b82f6', cursor: 'pointer' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
            <span>5% (OMC level)</span>
            <span>100% (National supply)</span>
          </div>
        </div>

        {/* Max Transit Time */}
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Max Acceptable Transit: {maxTransit} Days
          </label>
          <input
            type="range" min="5" max="45" step="1"
            value={maxTransit}
            onChange={e => setMaxTransit(parseInt(e.target.value))}
            style={{ width: '100%', accentColor: '#3b82f6', cursor: 'pointer' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
            <span>5 Days</span>
            <span>45 Days (Global limit)</span>
          </div>
        </div>
      </div>

      {/* Recommendations Panel */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
          Ranked Alternative Crude Sources
        </div>

        {loading && !data ? (
          <div style={{ height: 250, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
            <div style={{ width: 20, height: 20, borderRadius: '50%', border: '2px solid var(--border)', borderTopColor: '#3b82f6', animation: 'spin 0.8s linear infinite', marginRight: 8 }} />
            Evaluating alternative supply chains...
          </div>
        ) : data?.recommendations?.length ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* Table / List */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {data.recommendations.map((rec, i) => {
                const isExcluded = rec.is_sanctioned || rec.transit_days > maxTransit;
                const exclusionReason = rec.is_sanctioned
                  ? rec.sanction_note
                  : rec.transit_days > maxTransit
                    ? `Transit time (${rec.transit_days}d) exceeds maximum limit (${maxTransit}d)`
                    : null;

                return (
                  <div
                    key={rec.name}
                    style={{
                      padding: '12px 14px', borderRadius: 8,
                      border: '1px solid var(--border)',
                      background: isExcluded ? 'rgba(239,68,68,0.02)' : 'rgba(255,255,255,0.02)',
                      display: 'grid', gridTemplateColumns: '50px 1.5fr 1fr 1fr 80px',
                      alignItems: 'center', gap: 16,
                      opacity: isExcluded ? 0.45 : 1.0,
                    }}
                  >
                    {/* Rank */}
                    <div style={{ fontSize: 18, fontWeight: 700, color: isExcluded ? '#475569' : '#3b82f6', textAlign: 'center' }}>
                      {isExcluded ? '—' : `#${i + 1}`}
                    </div>

                    {/* Source info */}
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{rec.name}</div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Grade: {rec.crude_grade}</div>
                      {rec.route_corridors?.length > 0 && (
                        <div style={{ fontSize: 9, color: '#64748b', marginTop: 4 }}>
                          Route chokepoints: {rec.route_corridors.join(', ').toUpperCase()}
                        </div>
                      )}
                    </div>

                    {/* Key Attributes */}
                    <div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Transit Time</div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginTop: 2 }}>{rec.transit_days} Days</div>
                      <div style={{ fontSize: 9, color: '#475569' }}>Sourced from import_mix</div>
                    </div>

                    {/* Cost index & chokepoint risk */}
                    <div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Cost Discount / Premium</div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: rec.cost_source ? '#22c55e' : 'var(--text-primary)', marginTop: 2 }}>
                        {rec.cost_index}
                      </div>
                      {rec.cost_source && (
                        <div style={{ fontSize: 8, color: '#475569', marginTop: 2, maxWidth: 140 }} title={rec.cost_source}>
                          Source: {rec.cost_source}
                        </div>
                      )}
                    </div>

                    {/* Score / Exclusion badge */}
                    <div style={{ textAlign: 'right' }}>
                      {isExcluded ? (
                        <span style={{
                          fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
                          background: 'rgba(239,68,68,0.1)', color: '#ef4444',
                          border: '1px solid rgba(239,68,68,0.2)',
                        }} title={exclusionReason}>
                          EXCLUDED
                        </span>
                      ) : (
                        <div>
                          <div style={{ fontSize: 16, fontWeight: 700, color: '#3b82f6' }}>{rec.final_score.toFixed(0)}</div>
                          <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>Index</div>
                        </div>
                      )}
                    </div>

                    {/* Exclusion tooltip text */}
                    {isExcluded && exclusionReason && (
                      <div style={{ gridColumn: '1 / -1', fontSize: 10, color: '#ef4444', marginTop: 4 }}>
                        ⚠ {exclusionReason}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Transparent Scoring Formula */}
            <div style={{
              fontSize: 10, color: '#475569', lineHeight: 1.6,
              background: 'rgba(255,255,255,0.01)', borderRadius: 6,
              padding: '10px 12px', border: '1px solid var(--border)',
            }}>
              <div style={{ fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Transparent Scoring Algorithm
              </div>
              <div style={{ fontFamily: 'monospace', marginBottom: 4 }}>
                score = (transit_score * 40%) + (safety_score * 40%) + (reliability_score * 20%)
              </div>
              <div>• <strong>Transit Speed (40%)</strong>: computed as max(0, 100 - (transit_days - 5) * 100/35).</div>
              <div>• <strong>Chokepoint Safety (40%)</strong>: dynamically calculated as (100 - max(live_corridor_risk)) along the supplier's standard transit route. Currently, Strait of Hormuz risk is scored at 100.</div>
              <div>• <strong>Supplier Reliability (20%)</strong>: static baseline reliability. UAE (95), Saudi Arabia (95), USA (98), Iraq (85), Nigeria (70), Russia (60).</div>
              {data.sanctioned_countries_detected?.length > 0 && (
                <div style={{ color: '#ef4444', marginTop: 4 }}>
                  • <strong>OFAC Sanctions Check</strong>: dynamic exclusion triggered for {data.sanctioned_countries_detected.join(', ')} due to recent designates.
                </div>
              )}
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Error evaluating alternative crude sources.
          </div>
        )}
      </div>
    </div>
  );
}
