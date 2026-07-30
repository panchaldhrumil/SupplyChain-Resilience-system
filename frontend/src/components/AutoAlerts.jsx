

import { useState, useEffect, useCallback } from 'react';
import { ENDPOINTS, POLL_INTERVAL_MS } from '../config';

// ── Corridor display names
const CORRIDOR_LABELS = {
  hormuz: 'Strait of Hormuz',
  red_sea: 'Red Sea / Bab-el-Mandeb',
  suez: 'Suez Canal',
  cape_of_good_hope: 'Cape of Good Hope',
  russia_route: 'Russia / Black Sea',
  malacca: 'Strait of Malacca',
  india_domestic: 'India Domestic',
};

// ── Format relative timestamp
function relTime(isoStr) {
  if (!isoStr) return '';
  try {
    const diff = Date.now() - new Date(isoStr).getTime();
    const m = Math.floor(diff / 60000);
    if (m < 1) return 'just now';
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  } catch {
    return '';
  }
}

// ── Score badge
function ScoreBar({ prev, now, threshold }) {
  const p = parseFloat(prev) || 0;
  const n = parseFloat(now) || 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
      <span style={{ color: 'var(--text-muted)' }}>{p.toFixed(1)}</span>
      <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>→</span>
      <span style={{
        fontWeight: 700,
        color: '#ef4444',
        background: 'rgba(239,68,68,0.12)',
        padding: '1px 6px',
        borderRadius: 4,
      }}>{n.toFixed(1)}</span>
      <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>
        (threshold {parseFloat(threshold) || 66})
      </span>
    </div>
  );
}

// ── Single alert card
function AlertCard({ alert, idx }) {
  const [expanded, setExpanded] = useState(false);
  const [evidence, setEvidence] = useState([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);

  const corridorLabel = CORRIDOR_LABELS[alert.corridor] || alert.corridor;
  const latencyMs = alert.latency_ms;
  const sigScenMs = alert.signal_to_scenario_ms;
  const scenProcMs = alert.scenario_to_procurement_ms;
  const procLlmMs = alert.procurement_to_llm_ms;

  const topRec = alert.top_recommendation;
  const topScore = parseFloat(alert.top_score) || null;
  const covDays = parseFloat(alert.coverage_days) || null;
  const covNote = alert.coverage_note || (covDays == null ? 'No import share mapped for this corridor' : null);
  const suppliers = alert.all_affected_suppliers
    ? alert.all_affected_suppliers.split('|').filter(Boolean)
    : [];

  const isDomestic = alert.corridor === 'india_domestic';

  // Lazy fetch supporting evidence (top news articles driving the score)
  const toggleEvidence = async () => {
    if (!expanded && evidence.length === 0) {
      setEvidenceLoading(true);
      try {
        const res = await fetch(`${ENDPOINTS.newsFeed}?corridor=${alert.corridor}&limit=3`);
        const json = await res.json();
        setEvidence(json.items || []);
      } catch (err) {
        setEvidence([]);
      } finally {
        setEvidenceLoading(false);
      }
    }
    setExpanded(!expanded);
  };

  return (
    <div style={{
      background: 'var(--bg-code)',
      border: '1px solid rgba(239,68,68,0.25)',
      borderLeft: '3px solid #ef4444',
      borderRadius: 8,
      padding: '12px 14px',
      marginBottom: 10,
      position: 'relative',
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{
            background: '#ef4444', color: '#fff',
            fontSize: 9, fontWeight: 700, letterSpacing: '0.06em',
            padding: '2px 6px', borderRadius: 3,
          }}>🔴 ALERT</span>
          <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)' }}>
            {corridorLabel}
          </span>
          {isDomestic && (
            <span style={{ fontSize: 10, color: '#f59e0b', background: 'rgba(245,158,11,0.12)', padding: '1px 6px', borderRadius: 4, border: '1px solid rgba(245,158,11,0.2)' }}>
              Domestic Refined Product Risk
            </span>
          )}
        </div>
        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
          {relTime(alert.triggered_at)}
        </span>
      </div>

      {/* Score crossing */}
      <div style={{ marginBottom: 8 }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', marginRight: 6 }}>Score crossed threshold:</span>
        <ScoreBar prev={alert.score_prev} now={alert.score_now} threshold={alert.threshold} />
      </div>

      {/* Key metrics grid */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr',
        gap: 8, marginBottom: 8,
      }}>
        {/* Sub-step Latency Breakdown */}
        <div style={{
          background: 'rgba(59,130,246,0.1)',
          border: '1px solid rgba(59,130,246,0.2)',
          borderRadius: 6, padding: '6px 10px',
        }}>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>
            Signal → Rec Latency
          </div>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#3b82f6' }}>
            {latencyMs != null ? `${latencyMs} ms` : '—'}
          </div>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2, lineHeight: 1.3 }}>
            {sigScenMs != null ? `Signal→Scen: ${sigScenMs}ms` : 'Perceive & Calc'}
            {scenProcMs != null && ` · Rec: ${scenProcMs}ms`}
            {procLlmMs > 0 && ` · LLM: ${procLlmMs}ms`}
          </div>
        </div>

        {/* Top procurement rec */}
        <div style={{
          background: 'rgba(34,197,94,0.08)',
          border: '1px solid rgba(34,197,94,0.2)',
          borderRadius: 6, padding: '6px 10px', textAlign: 'center',
        }}>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>
            Top Alternative
          </div>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#22c55e' }}>
            {topRec || '—'}
          </div>
          {topScore != null && (
            <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>score {topScore.toFixed(1)}/100</div>
          )}
        </div>

        {/* Buffer coverage with explicit fallback note */}
        <div style={{
          background: 'rgba(251,191,36,0.08)',
          border: '1px solid rgba(251,191,36,0.2)',
          borderRadius: 6, padding: '6px 10px', textAlign: 'center',
        }}>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>
            Buffer Coverage
          </div>
          {covDays != null ? (
            <div style={{ fontSize: 13, fontWeight: 700, color: '#fbbf24' }}>
              {covDays.toFixed(1)} days
            </div>
          ) : (
            <div style={{ fontSize: 9, color: '#f59e0b', fontWeight: 600, lineHeight: 1.3 }}>
              {covNote}
            </div>
          )}
        </div>
      </div>

      {/* Affected suppliers line */}
      {suppliers.length > 0 && (
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 6 }}>
          Affected suppliers: {suppliers.join(', ')}
        </div>
      )}

      {/* Item 3: Supporting Evidence Expandable Trail */}
      <div style={{ marginTop: 8, borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 6 }}>
        <button
          onClick={toggleEvidence}
          style={{
            background: 'transparent', border: 'none', color: '#3b82f6',
            fontSize: 11, fontWeight: 600, cursor: 'pointer', padding: 0,
            display: 'flex', alignItems: 'center', gap: 4,
          }}
        >
          <span>{expanded ? '▼' : '▶'}</span>
          <span>Why was this triggered? (Supporting News Trail)</span>
        </button>

        {expanded && (
          <div style={{ marginTop: 8, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 6, padding: 10 }}>
            {evidenceLoading && (
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Loading contributing news articles…</div>
            )}
            {!evidenceLoading && evidence.length === 0 && (
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>No specific headline citations logged for this cycle.</div>
            )}
            {!evidenceLoading && evidence.map((art, i) => (
              <div key={i} style={{ borderLeft: '2px solid #ef4444', paddingLeft: 8, marginBottom: 6, fontSize: 11 }}>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                  {art.link ? (
                    <a href={art.link} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-primary)', textDecoration: 'none' }}>
                      [{i + 1}] {art.title}
                    </a>
                  ) : `[${i + 1}] ${art.title}`}
                </div>
                <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2 }}>
                  {art.source} · {art.date ? new Date(art.date).toLocaleDateString() : ''} · Severity: {art.severity}/5
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

import { usePolling } from '../hooks/usePolling';

// ── Main component
export default function AutoAlerts() {
  const fetchFn = useCallback(() => fetch(`${ENDPOINTS.autoAlerts}?limit=10`).then(r => r.json()), []);
  const { data, loading, error, lastUpdated: lastTs } = usePolling(fetchFn, POLL_INTERVAL_MS);

  const alerts = data?.alerts || [];
  const threshold = data?.threshold || 66;

  const headerRight = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      {lastTs && (
        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
          Updated {lastTs.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      )}
      <span style={{
        fontSize: 10, background: 'rgba(239,68,68,0.12)',
        color: '#ef4444', padding: '2px 8px', borderRadius: 4,
        border: '1px solid rgba(239,68,68,0.2)',
      }}>
        Threshold ≥ {threshold}
      </span>
    </div>
  );

  return (
    <div className="card" style={{ borderTop: '2px solid #ef4444' }}>
      {/* Card header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
        <div className="card-title" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>⚡</span> Live Alerts
          {alerts.length > 0 && (
            <span style={{
              fontSize: 11, background: '#ef4444', color: '#fff',
              borderRadius: '50%', width: 18, height: 18,
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              fontWeight: 700,
            }}>{alerts.length}</span>
          )}
        </div>
        {headerRight}
      </div>

      {/* Description */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12, lineHeight: 1.5 }}>
        Auto-generated by the Disruption Response Agent. Fires when a corridor score crosses{' '}
        <strong>{threshold}</strong> for the first time. Includes end-to-end latency from
        signal detection to procurement recommendation.
      </div>

      {/* States */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text-muted)', fontSize: 12 }}>
          <div style={{
            width: 14, height: 14, borderRadius: '50%',
            border: '2px solid var(--border)', borderTopColor: '#ef4444',
            animation: 'spin 0.8s linear infinite',
            display: 'inline-block', marginRight: 8,
          }} />
          Loading alerts…
        </div>
      )}

      {!loading && error && (
        <div style={{
          background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
          borderRadius: 6, padding: 12, fontSize: 12, color: '#ef4444',
        }}>
          {error}
        </div>
      )}

      {!loading && !error && alerts.length === 0 && (
        <div style={{
          background: 'var(--bg-overlay)',
          border: '1px solid var(--border)',
          borderRadius: 8, padding: '20px 16px', textAlign: 'center',
        }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>🟢</div>
          <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)', marginBottom: 4 }}>
            No automated alerts yet
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6, maxWidth: 340, margin: '0 auto' }}>
            {data?.note || (
              <>
                The agent monitors corridor scores every 5 minutes.
                It will fire an alert the first time any corridor crosses the{' '}
                <strong>{threshold}</strong> threshold.
                Run <code style={{ fontSize: 10 }}>python live_macro_pipeline.py</code> to
                populate corridor scores.
              </>
            )}
          </div>
        </div>
      )}

      {!loading && !error && alerts.length > 0 && (
        <div>
          {alerts.map((alert, i) => (
            <AlertCard key={`${alert.cycle_id}-${alert.corridor}-${i}`} alert={alert} idx={i} />
          ))}
        </div>
      )}

      {/* Footer source line */}
      <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-footer)' }}>
        Source: auto_triggered_alerts.csv · agent/response_agent.py
      </div>
    </div>
  );
}
