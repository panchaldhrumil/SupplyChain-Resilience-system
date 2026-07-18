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
    let corridorKey = '';
    if (scenarioId === 'hormuz_closure') corridorKey = 'hormuz';
    if (scenarioId === 'suez_blockage') corridorKey = 'suez';

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
            <option value="hormuz_closure">Strait of Hormuz Closure</option>
            <option value="suez_blockage">Suez Canal Blockage</option>
            <option value="spr_release">Strategic Reserve (SPR) Drawdown</option>
            <option value="omc_import_cut">General OMC Import Cut</option>
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
                {scenarioId === 'hormuz_closure' ? 'Strait of Hormuz' : 'Suez Canal'}
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
            {/* Impact Panels */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {/* Refinery Run-rate Impact */}
              <div style={{
                padding: '12px 14px', borderRadius: 8,
                background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)',
              }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Refinery Run-rate Impact
                </div>
                <div style={{ fontSize: 24, fontWeight: 700, marginTop: 8, fontVariantNumeric: 'tabular-nums', color: simData.refinery_runrate_impact_pct === null ? '#f59e0b' : '#ef4444' }}>
                  {simData.refinery_runrate_impact_pct === null ? (
                    'PENDING'
                  ) : (
                    `${simData.refinery_runrate_impact_pct.toFixed(1)}%`
                  )}
                </div>
                <div style={{ fontSize: 10, color: '#475569', marginTop: 4 }}>
                  {simData.refinery_runrate_impact_pct === null ? (
                    'Configure shares in import_mix.json'
                  ) : (
                    `Based on chokepoint share of ${simData.corridor_share_pct}%`
                  )}
                </div>
              </div>

              {/* Retail Fuel Price Impact */}
              <div style={{
                padding: '12px 14px', borderRadius: 8,
                background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)',
              }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Retail Fuel Price Impact
                </div>
                <div style={{ fontSize: 24, fontWeight: 700, marginTop: 8, fontVariantNumeric: 'tabular-nums', color: simData.retail_price_impact_pct === null ? '#f59e0b' : '#f59e0b' }}>
                  {simData.retail_price_impact_pct === null ? (
                    'PENDING'
                  ) : (
                    `+${simData.retail_price_impact_pct.toFixed(1)}%`
                  )}
                </div>
                <div style={{ fontSize: 10, color: '#475569', marginTop: 4 }}>
                  {simData.retail_price_impact_pct === null ? (
                    'Configure shares in import_mix.json'
                  ) : (
                    `Using elasticity factor of ${simData.elasticity_assumption}`
                  )}
                </div>
              </div>
            </div>

            {/* Coverage Pass/Fail Result */}
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
                      Reserves can withstand this supply shortfall for the entire <strong>{duration} days</strong>.{' '}
                      Combined reserves will last for <strong>{simData.coverage.total_cover_days} days</strong>.
                    </>
                  ) : (
                    <>
                      Combined reserve buffer <span style={{ color: '#ef4444', fontWeight: 600 }}>will exhaust in {simData.coverage.total_cover_days} days</span>.{' '}
                      Disruption outlasts reserves by <strong>{Math.abs(simData.coverage.total_difference_days)} days</strong>.
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
                ) : (
                  '⚠ Shortfall calculations pending configuration of import shares in import_mix.json.'
                )}
              </div>
            )}

            {/* Assumptions Audit Log */}
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
                <div>• Corridor Import Share: {scenarioId === 'hormuz_closure' ? 'Arabian Gulf' : 'Suez route'} routes transit {simData.corridor_share_pct}% of crude.</div>
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
