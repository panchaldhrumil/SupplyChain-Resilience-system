// ProcurementEngine.jsx — Module 3 (Procurement Recommendation Engine)
// Dynamic weighted alternatives ranking calling /api/procurement-recommend.
import { useState, useEffect } from 'react';
import { API_BASE } from '../config';

// Maps corridor IDs to human-readable labels for route highlighting
const CORRIDOR_LABELS = {
  hormuz:            'strait of hormuz',
  suez:              'suez canal',
  russia_route:      'russia',
  cape_of_good_hope: 'cape of good hope',
  red_sea:           'red sea',
  bab_el_mandeb:     'bab-el-mandeb',
  malacca:           'malacca',
};

export default function ProcurementEngine() {
  const [disruptedId, setDisruptedId]   = useState('Saudi Arabia');
  const [volumePct, setVolumePct]       = useState(20);
  const [maxTransit, setMaxTransit]     = useState(30);
  const [data, setData]                 = useState(null);
  const [loading, setLoading]           = useState(false);

  // Status message cycling during fetch
  const [loadingMsgIdx, setLoadingMsgIdx] = useState(0);
  const LOADING_MESSAGES = [
    'Ranking alternative crude supply sources…',
    'Evaluating transit times & chokepoint safety…',
    'Calculating weighted resilience scores…',
    'Generating Gemini LLM procurement justifications…',
  ];

  useEffect(() => {
    if (!loading) {
      setLoadingMsgIdx(0);
      return;
    }
    const timer = setInterval(() => {
      setLoadingMsgIdx(idx => (idx + 1) % LOADING_MESSAGES.length);
    }, 2500);
    return () => clearInterval(timer);
  }, [loading]);

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
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16, opacity: loading ? 0.75 : 1.0, transition: 'opacity 0.2s' }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', borderBottom: '1px solid var(--border)', paddingBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Disruption Context</span>
          {loading && (
            <span style={{ fontSize: 10, color: '#3b82f6', fontWeight: 600 }}>🔒 Controls Locked</span>
          )}
        </div>

        {/* Disrupted Supplier / Corridor */}
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Disrupted Node / Source
          </label>
          <select
            value={disruptedId}
            disabled={loading}
            onChange={e => setDisruptedId(e.target.value)}
            style={{
              width: '100%', background: 'var(--bg-input)', border: '1px solid var(--border-input)',
              color: 'var(--text-primary)', borderRadius: 8, padding: '10px 12px', fontSize: 13,
              cursor: loading ? 'not-allowed' : 'pointer',
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
            disabled={loading}
            onChange={e => setVolumePct(parseInt(e.target.value))}
            style={{ width: '100%', accentColor: '#3b82f6', cursor: loading ? 'not-allowed' : 'pointer' }}
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
            disabled={loading}
            onChange={e => setMaxTransit(parseInt(e.target.value))}
            style={{ width: '100%', accentColor: '#3b82f6', cursor: loading ? 'not-allowed' : 'pointer' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
            <span>5 Days</span>
            <span>45 Days (Global limit)</span>
          </div>
        </div>

        {/* Corridor disruption indicator */}
        {data?.disrupted_corridor_applied && !loading && (
          <div style={{
            padding: '8px 12px', borderRadius: 6,
            background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
            fontSize: 10, color: '#f87171',
          }}>
            🚨 Corridor <strong>{disruptedId.toUpperCase()}</strong> forced to risk=100 in scoring.
            All suppliers routing through this chokepoint are penalised.
          </div>
        )}
      </div>

      {/* Recommendations Panel */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', borderBottom: '1px solid var(--border)', paddingBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Ranked Alternative Crude Sources</span>
          {loading && (
            <span style={{ fontSize: 11, color: '#3b82f6', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', border: '2px solid #3b82f6', borderTopColor: 'transparent', animation: 'spin 0.8s linear infinite', display: 'inline-block' }} />
              {LOADING_MESSAGES[loadingMsgIdx]}
            </span>
          )}
        </div>

        {loading ? (
          /* Skeleton loading card placeholders */
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[1, 2, 3, 4].map(idx => (
              <div
                key={idx}
                style={{
                  padding: '16px 14px', borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'var(--bg-code)',
                  display: 'grid', gridTemplateColumns: '50px 1.5fr 1fr 1fr 100px',
                  alignItems: 'center', gap: 16, opacity: 0.6,
                  animation: 'pulse 1.5s ease-in-out infinite',
                }}
              >
                <div style={{ height: 24, width: 24, borderRadius: '50%', background: 'var(--border)', margin: '0 auto' }} />
                <div>
                  <div style={{ height: 14, width: '70%', background: 'var(--border)', borderRadius: 4, marginBottom: 6 }} />
                  <div style={{ height: 10, width: '40%', background: 'var(--border)', borderRadius: 3 }} />
                </div>
                <div>
                  <div style={{ height: 10, width: '50%', background: 'var(--border)', borderRadius: 3, marginBottom: 6 }} />
                  <div style={{ height: 12, width: '60%', background: 'var(--border)', borderRadius: 4 }} />
                </div>
                <div>
                  <div style={{ height: 10, width: '50%', background: 'var(--border)', borderRadius: 3, marginBottom: 6 }} />
                  <div style={{ height: 12, width: '60%', background: 'var(--border)', borderRadius: 4 }} />
                </div>
                <div style={{ height: 32, width: '80%', background: 'var(--border)', borderRadius: 6, margin: '0 auto' }} />
              </div>
            ))}
          </div>
        ) : data?.recommendations?.length ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* Scoring Errors Alert */}
            {data.scoring_errors?.length > 0 && (
              <div style={{
                padding: '10px 12px', borderRadius: 6,
                background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
                fontSize: 11, color: '#f87171', marginBottom: 10
              }}>
                <strong>Warning:</strong> Some alternative sources failed to score and were skipped:
                <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                  {data.scoring_errors.map((err, ei) => (
                    <li key={ei}>{err.country}: {err.error}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Recommendation Cards */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {data.recommendations.map((rec, i) => {
                const isTransitExcluded  = rec.transit_days > maxTransit;
                const isSanctionCaution  = rec.is_sanctioned;
                const exclusionReason    = isTransitExcluded
                  ? `Transit time (${rec.transit_days}d) exceeds maximum limit (${maxTransit}d)`
                  : null;

                // Determine which route segments to highlight red (disrupted chokepoint)
                const disruptedCorridor = data.disrupted_corridor_applied || '';
                const disruptedLabel    = CORRIDOR_LABELS[disruptedCorridor] || '';
                const routePassesThroughDisruption = disruptedLabel &&
                  rec.route?.chokepoints?.some(cp => cp === disruptedCorridor);

                return (
                  <div
                    key={rec.name}
                    style={{
                      padding: '12px 14px', borderRadius: 8,
                      border: `1px solid ${isSanctionCaution ? 'rgba(245,158,11,0.25)' : 'var(--border)'}`,
                      background: isTransitExcluded
                        ? 'rgba(239,68,68,0.02)'
                        : isSanctionCaution
                          ? 'rgba(245,158,11,0.03)'
                          : 'rgba(255,255,255,0.02)',
                      opacity: isTransitExcluded ? 0.45 : 1.0,
                    }}
                  >
                    {/* Top row: rank / name / transit / cost / score */}
                    <div style={{
                      display: 'grid', gridTemplateColumns: '50px 1.5fr 1fr 1fr 100px',
                      alignItems: 'center', gap: 16,
                    }}>
                      {/* Rank */}
                      <div style={{ fontSize: 18, fontWeight: 700, color: isTransitExcluded ? '#475569' : '#3b82f6', textAlign: 'center' }}>
                        {isTransitExcluded ? '—' : `#${i + 1}`}
                      </div>

                      {/* Source info */}
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{rec.name}</div>
                        <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Grade: {rec.crude_grade}</div>
                        {routePassesThroughDisruption && (
                          <div style={{ fontSize: 9, color: '#f87171', marginTop: 2, fontWeight: 600 }}>
                            ⚠ Routes through disrupted corridor
                          </div>
                        )}
                      </div>

                      {/* Transit Time */}
                      <div>
                        <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Transit Time</div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginTop: 2 }}>{rec.transit_days} Days</div>
                        <div style={{ fontSize: 9, color: '#475569' }}>Sourced from import_mix</div>
                      </div>

                      {/* Cost index */}
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

                      {/* Score / Badge column */}
                      <div style={{ textAlign: 'right' }}>
                        {isTransitExcluded ? (
                          <span style={{
                            fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
                            background: 'rgba(239,68,68,0.1)', color: '#ef4444',
                            border: '1px solid rgba(239,68,68,0.2)',
                          }} title={exclusionReason}>
                            EXCLUDED
                          </span>
                        ) : (
                          <div>
                            {isSanctionCaution && (
                              <div style={{
                                fontSize: 8, fontWeight: 700, padding: '2px 6px', borderRadius: 3, marginBottom: 4,
                                background: 'rgba(245,158,11,0.15)', color: '#f59e0b',
                                border: '1px solid rgba(245,158,11,0.35)', whiteSpace: 'nowrap',
                              }}>
                                ⚠ SANCTIONS CAUTION
                              </div>
                            )}
                            <div style={{ fontSize: 16, fontWeight: 700, color: isSanctionCaution ? '#f59e0b' : '#3b82f6' }}>
                              {rec.final_score.toFixed(0)}
                            </div>
                            <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>Index</div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Sanctions caution note */}
                    {isSanctionCaution && rec.sanction_note && (
                      <div style={{ fontSize: 10, color: '#f59e0b', marginTop: 8, paddingTop: 6, borderTop: '1px solid rgba(245,158,11,0.15)' }}>
                        ⚠ {rec.sanction_note}
                      </div>
                    )}

                    {/* Transit exclusion note */}
                    {isTransitExcluded && exclusionReason && (
                      <div style={{ fontSize: 10, color: '#ef4444', marginTop: 6 }}>
                        ⚠ {exclusionReason}
                      </div>
                    )}

                    {/* ── Route Path Stepper */}
                    {rec.route?.route_path?.length > 0 && (
                      <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
                        <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>
                          Shipping Route · {rec.route.origin_port}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
                          {rec.route.route_path.map((segment, si) => {
                            // Is this segment a known chokepoint on this route?
                            const isChokepoint = rec.route.chokepoints?.some(cp => {
                              const label = CORRIDOR_LABELS[cp] || cp.replace(/_/g, ' ');
                              return segment.toLowerCase().includes(label) ||
                                     label.includes(segment.toLowerCase().split(' ')[0]);
                            });
                            // Is this chokepoint the disrupted one?
                            const isDisruptedSegment = disruptedLabel &&
                              isChokepoint &&
                              rec.route.chokepoints?.some(cp =>
                                cp === disruptedCorridor &&
                                (segment.toLowerCase().includes(CORRIDOR_LABELS[cp] || '') ||
                                 segment.toLowerCase().includes(cp.replace(/_/g, ' ')))
                              );

                            return (
                              <span key={si} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                <span style={{
                                  fontSize: 9, padding: '2px 7px', borderRadius: 3,
                                  fontWeight: isChokepoint ? 700 : 400,
                                  background: isDisruptedSegment
                                    ? 'rgba(239,68,68,0.18)'
                                    : isChokepoint
                                      ? 'rgba(245,158,11,0.12)'
                                      : 'rgba(255,255,255,0.04)',
                                  color: isDisruptedSegment
                                    ? '#f87171'
                                    : isChokepoint
                                      ? '#fbbf24'
                                      : '#64748b',
                                  border: isDisruptedSegment
                                    ? '1px solid rgba(239,68,68,0.35)'
                                    : isChokepoint
                                      ? '1px solid rgba(245,158,11,0.3)'
                                      : '1px solid transparent',
                                }}>
                                  {segment}
                                </span>
                                {si < rec.route.route_path.length - 1 && (
                                  <span style={{ fontSize: 8, color: '#475569' }}>→</span>
                                )}
                              </span>
                            );
                          })}
                        </div>
                        {rec.route._confidence === 'estimated' && (
                          <div style={{ fontSize: 8, color: '#475569', marginTop: 4, fontStyle: 'italic' }}>
                            Route: estimated — not from live AIS tracking
                          </div>
                        )}
                      </div>
                    )}

                    {/* LLM Justification */}
                    {rec.justification && (
                      <div style={{ marginTop: 8, fontSize: 10, color: '#94a3b8', fontStyle: 'italic', paddingTop: 6, borderTop: '1px solid var(--border)' }}>
                        💡 {rec.justification}
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
                score = (transit_score × 40%) + (safety_score × 40%) + (reliability_score × 20%)
              </div>
              <div>• <strong>Transit Speed (40%)</strong>: max(0, 100 − (transit_days − 5) × 100/35).</div>
              <div>• <strong>Chokepoint Safety (40%)</strong>: 100 − max(live_corridor_risk for route chokepoints). When a corridor is selected as disrupted, its risk is forced to 100.</div>
              <div>• <strong>Supplier Reliability (20%)</strong>: baseline reliability — UAE (95), Saudi (95), USA (98), Iraq (85), Kuwait (90), Nigeria (70), Russia (60).</div>
              {data.sanctioned_countries_detected?.length > 0 && (
                <div style={{ color: '#f59e0b', marginTop: 4 }}>
                  • <strong>OFAC Sanctions Penalty</strong>: {data.sanctioned_countries_detected.join(', ')} carry active SDN designations.
                  Score penalised (not excluded) — multiplier configurable via <code>sanctions_config</code> in scenario_assumptions.json.
                </div>
              )}
              {data.disrupted_corridor_applied && (
                <div style={{ color: '#f87171', marginTop: 4 }}>
                  • <strong>Corridor Disruption</strong>: <code>{data.disrupted_corridor_applied}</code> risk forced to 100.
                  All suppliers whose route traverses this corridor receive safety_score = 0.
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
