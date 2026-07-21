// ScenarioSimulator.jsx — Module 2 (Scenario Simulator)
// Deterministic policy simulator calling /api/scenario-simulate backend endpoint.
import { useState, useEffect } from 'react';
import { API_BASE } from '../config';

export default function ScenarioSimulator({ corridors }) {
  const [scenarioId, setScenarioId]   = useState('hormuz_closure');
  const [severity, setSeverity]       = useState(0.2); // default 20%
  const [duration, setDuration]       = useState(30);  // default 30 days
  const [simData, setSimData]         = useState(null);
  const [loading, setLoading]         = useState(false);

  // Sync with API
  useEffect(() => {
    const controller = new AbortController();
    const fetchSim = async () => {
      setLoading(true);
      try {
        const url = `${API_BASE}/api/scenario-simulate?scenario_id=${scenarioId}&severity=${severity}&duration_days=${duration}`;
        const res = await fetch(url, { signal: controller.signal });
        const json = await res.json();
        setSimData(json);
      } catch (e) {
        if (e.name !== 'AbortError') {
          console.error(e);
        }
      } finally {
        setLoading(false);
      }
    };
    fetchSim();
    return () => controller.abort();
  }, [scenarioId, severity, duration]);

  // Find live risk score for corresponding corridor
  const getLiveCorridorRisk = () => {
    const scenarioCorridorMap = {
      hormuz_closure:              'hormuz',
      suez_blockage:               'suez',
      persian_gulf_conflict:       'hormuz',
      red_sea_disruption:          'suez',           // closest tracked proxy for Bab-el-Mandeb
      russia_sanctions_escalation: 'russia_route',
    };
    const corridorKey = scenarioCorridorMap[scenarioId] || '';
    if (!corridorKey) return null;
    const c = corridors.find(x => x.corridor === corridorKey);
    return c ? { score: c.score, level: c.level } : null;
  };

  const liveRisk = getLiveCorridorRisk();

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '350px 1fr', gap: '1.5rem' }}>
      {/* Inputs column */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
          Simulation Parameters
        </div>

        {/* Scenario Select */}
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Select Scenario
          </label>
          <select
            value={scenarioId}
            onChange={e => setScenarioId(e.target.value)}
            style={{
              width: '100%', background: 'var(--bg-input)', border: '1px solid var(--border-input)',
              color: 'var(--text-primary)', borderRadius: 8, padding: '10px 12px', fontSize: 13,
              cursor: 'pointer',
            }}
          >
            <optgroup label="── Physical Corridor Disruptions">
              <option value="hormuz_closure">Strait of Hormuz Closure</option>
              <option value="suez_blockage">Suez Canal Blockage</option>
              <option value="red_sea_disruption">Red Sea / Bab-el-Mandeb (Houthi)</option>
              <option value="persian_gulf_conflict">Persian Gulf Regional Conflict</option>
            </optgroup>
            <optgroup label="── Political / Sanctions">
              <option value="russia_sanctions_escalation">Russia Sanctions Escalation</option>
              <option value="opec_production_cut">OPEC+ Production Cut</option>
              <option value="omc_import_cut">General OMC Import Curtailment</option>
            </optgroup>
            <optgroup label="── Domestic / Financial">
              <option value="domestic_refinery_outage">Domestic Refinery Outage</option>
              <option value="rupee_depreciation_shock">Rupee Depreciation Shock (₹/USD)</option>
              <option value="spr_release">Strategic Reserve (SPR) Drawdown</option>
            </optgroup>
          </select>
        </div>

        {/* Severity Input */}
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Severity: {(severity * 100).toFixed(0)}%
          </label>
          <input
            type="range" min="0.1" max="1.0" step="0.1"
            value={severity}
            onChange={e => setSeverity(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: '#f59e0b', cursor: 'pointer' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
            <span>Partial (10%)</span>
            <span>Full (100%)</span>
          </div>
        </div>

        {/* Duration Input */}
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Scenario Duration
          </label>
          <select
            value={duration}
            onChange={e => setDuration(parseInt(e.target.value))}
            style={{
              width: '100%', background: 'var(--bg-input)', border: '1px solid var(--border-input)',
              color: 'var(--text-primary)', borderRadius: 8, padding: '10px 12px', fontSize: 13,
              cursor: 'pointer',
            }}
          >
            <option value="7">7 Days (Short Term)</option>
            <option value="30">30 Days (Medium Term)</option>
            <option value="90">90 Days (Extended)</option>
          </select>
        </div>

        {/* Live Corridor Linkage */}
        {liveRisk && (
          <div style={{
            marginTop: 10, padding: '10px 12px', borderRadius: 8,
            background: 'var(--bg-base)', border: '1px solid var(--border)',
          }}>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Live Corridor Status
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                {({
                  hormuz_closure:              'Strait of Hormuz',
                  persian_gulf_conflict:       'Strait of Hormuz',
                  suez_blockage:               'Suez Canal',
                  red_sea_disruption:          'Suez / Red Sea (proxy)',
                  russia_sanctions_escalation: 'Russia Maritime Route',
                })[scenarioId] || 'Corridor'}
              </span>
              <span className={`badge badge-${liveRisk.level}`}>
                {liveRisk.score.toFixed(0)} RISK
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Outputs column */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
          Simulated Impacts
        </div>
        {loading && !simData ? (
          <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
            <div style={{ width: 20, height: 20, borderRadius: '50%', border: '2px solid var(--border)', borderTopColor: '#f59e0b', animation: 'spin 0.8s linear infinite', marginRight: 8 }} />
            Running simulation models...
          </div>
        ) : simData ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* ── Cost Shock: Rupee Depreciation — no volume disruption */}
            {simData.extra_impact?.type === 'cost_shock' ? (
              <div style={{
                padding: '16px', borderRadius: 8,
                background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)',
              }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                  Import Cost Increase — Rupee Terms
                </div>
                <div style={{ fontSize: 32, fontWeight: 700, color: '#f59e0b', fontVariantNumeric: 'tabular-nums' }}>
                  +{simData.extra_impact.import_cost_increase_pct}%
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8, lineHeight: 1.6 }}>
                  {simData.extra_impact.description}
                </div>
              </div>
            ) : (
              /* ── Standard Volume-Shock Impact Panels */
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                {/* Refinery Run-rate Impact */}
                <div style={{ padding: '12px 14px', borderRadius: 8, background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    Refinery Run-rate Impact
                  </div>
                  <div style={{ fontSize: 24, fontWeight: 700, marginTop: 8, fontVariantNumeric: 'tabular-nums', color: simData.refinery_runrate_impact_pct === null ? '#f59e0b' : '#ef4444' }}>
                    {simData.refinery_runrate_impact_pct === null ? 'PENDING' : `${simData.refinery_runrate_impact_pct.toFixed(1)}%`}
                  </div>
                  <div style={{ fontSize: 10, color: '#475569', marginTop: 4 }}>
                    {simData.refinery_runrate_impact_pct === null
                      ? 'Configure shares in import_mix.json'
                      : `Gap: ${simData.corridor_share_pct ?? simData.supply_gap_pct}% of daily imports`}
                  </div>
                </div>

                {/* Retail Fuel Price Impact */}
                <div style={{ padding: '12px 14px', borderRadius: 8, background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    Retail Fuel Price Impact
                  </div>
                  <div style={{ fontSize: 24, fontWeight: 700, marginTop: 8, fontVariantNumeric: 'tabular-nums', color: '#f59e0b' }}>
                    {simData.retail_price_impact_pct === null ? 'PENDING' : `+${simData.retail_price_impact_pct.toFixed(1)}%`}
                  </div>
                  <div style={{ fontSize: 10, color: '#475569', marginTop: 4 }}>
                    {simData.retail_price_impact_pct === null
                      ? 'Configure shares in import_mix.json'
                      : `Using elasticity factor of ${simData.elasticity_assumption}`}
                  </div>
                </div>
              </div>
            )}

            {/* ── Scenario-Specific Context Panel */}
            {simData.extra_impact?.type && simData.extra_impact.type !== 'cost_shock' && (
              <div style={{
                padding: '12px 14px', borderRadius: 8,
                background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.2)',
              }}>
                <div style={{ fontSize: 10, color: '#60a5fa', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6, fontWeight: 700 }}>
                  {simData.extra_impact.type === 'sanctions_shock'        ? '⚠ Sanctions Linkage' :
                   simData.extra_impact.type === 'transit_shock'          ? '⛴ Transit Disruption Detail' :
                   simData.extra_impact.type === 'multi_supplier_shock'   ? '🌐 Multi-Supplier Impact' :
                   simData.extra_impact.type === 'price_and_volume_shock' ? '📉 OPEC Price + Volume Shock' :
                   simData.extra_impact.type === 'domestic_shock'         ? '🏭 Domestic Constraint' :
                                                                             'Scenario Context'}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-primary)', lineHeight: 1.6 }}>
                  {simData.extra_impact.description}
                </div>
                {simData.extra_impact.affected_countries && (
                  <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {simData.extra_impact.affected_countries.map(c => (
                      <span key={c} style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(239,68,68,0.15)', color: '#f87171', fontWeight: 600 }}>{c}</span>
                    ))}
                    {simData.extra_impact.combined_share_pct && (
                      <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(245,158,11,0.15)', color: '#fbbf24', fontWeight: 600 }}>
                        Combined: {simData.extra_impact.combined_share_pct}% of imports
                      </span>
                    )}
                  </div>
                )}
                {simData.extra_impact.type === 'transit_shock' && (
                  <div style={{ marginTop: 8, fontSize: 11, color: '#94a3b8' }}>
                    🔄 Reroute via: <strong style={{ color: '#60a5fa' }}>{simData.extra_impact.reroute_via}</strong>
                    &nbsp;|&nbsp; +{simData.extra_impact.transit_extension_days} transit days
                  </div>
                )}
                {simData.extra_impact.type === 'sanctions_shock' && (
                  <div style={{ marginTop: 6, fontSize: 11, color: '#94a3b8' }}>
                    Supplier share at risk: <strong style={{ color: '#f87171' }}>{simData.extra_impact.supplier_share_pct}%</strong> of India's imports
                    &nbsp;|&nbsp; OFAC SDN watchlist active
                  </div>
                )}
              </div>
            )}

            {/* ── Buffer Coverage Pass/Fail */}
            {simData.coverage ? (
              <div style={{
                padding: '14px 16px', borderRadius: 8,
                background: simData.coverage.total_sufficient ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
                border: `1px solid ${simData.coverage.total_sufficient ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}`,
              }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: simData.coverage.total_sufficient ? '#22c55e' : '#ef4444', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>{simData.coverage.total_sufficient ? '✓' : '✗'}</span>
                  <span>{simData.coverage.total_sufficient ? 'BUFFER SUFFICIENT' : 'BUFFER INSUFFICIENT'}</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-primary)', marginTop: 6, lineHeight: 1.4 }}>
                  {simData.coverage.total_sufficient ? (
                    <>
                      At this gap rate, reserves can sustain supply for up to{' '}
                      <strong>{simData.coverage.total_cover_days} days</strong> — well beyond
                      this <strong>{duration}-day</strong> disruption window.
                      {simData.coverage.reserves_consumed_pct != null && (
                        <span style={{ display: 'block', marginTop: 6, fontSize: 11, color: '#94a3b8' }}>
                          This disruption consumes{' '}
                          <strong style={{ color: '#22c55e' }}>{simData.coverage.reserves_consumed_pct}%</strong>
                          {' '}of total reserve buffer.
                        </span>
                      )}
                    </>
                  ) : (
                    <>
                      Combined reserve buffer{' '}
                      <span style={{ color: '#ef4444', fontWeight: 600 }}>will exhaust in {simData.coverage.total_cover_days} days</span>.{' '}
                      Disruption outlasts reserves by{' '}
                      <strong>{Math.abs(simData.coverage.total_difference_days)} days</strong>.
                      {simData.coverage.reserves_consumed_pct != null && (
                        <span style={{ display: 'block', marginTop: 6, fontSize: 11, color: '#94a3b8' }}>
                          Reserve drawdown required:{' '}
                          <strong style={{ color: '#ef4444' }}>
                            {Math.min(simData.coverage.reserves_consumed_pct, 100).toFixed(1)}%
                          </strong>
                          {' '}of total buffer (exceeds 100% — full depletion).
                        </span>
                      )}
                    </>
                  )}
                </div>
              </div>
            ) : (
              <div style={{
                padding: '12px 14px', borderRadius: 8,
                background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)',
                fontSize: 11, color: '#f59e0b', lineHeight: 1.4,
              }}>
                {scenarioId === 'spr_release' ? (
                  '✓ SPR Release represents a supply injection — refinery operations remain unaffected and no supply gap is created.'
                ) : scenarioId === 'rupee_depreciation_shock' ? (
                  '✓ Rupee depreciation creates a cost shock, not a volume shortfall — no reserve drawdown is triggered by this scenario.'
                ) : (
                  '⚠ Shortfall calculations pending configuration of import shares in import_mix.json.'
                )}
              </div>
            )}

            {/* ── Assumptions Audit Log */}
            <div style={{
              fontSize: 10, color: '#475569', lineHeight: 1.6,
              background: 'rgba(255,255,255,0.01)', borderRadius: 6,
              padding: '10px 12px', border: '1px solid var(--border)',
            }}>
              <div style={{ fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Explicit Policy Assumptions
              </div>
              <div>• Retail Price Elasticity: {simData.elasticity_citation}</div>
              {simData.corridor_share_pct !== null && (
                <div>• Affected Import Share: {simData.corridor_share_pct}% of India's crude transits the disrupted route/supplier group.</div>
              )}
              <div>• Reserve capacity reference: 6.1 days cover in Strategic Reserve, 64.5 days cover in Refinery depot stocks.</div>
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Error loading simulation models.
          </div>
        )}
      </div>
    </div>
  );
}
