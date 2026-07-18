/**
 * CorridorBrief.jsx
 * 
 * RAG-grounded 2-3 sentence intelligence brief for a selected corridor.
 * Calls GET /api/corridor-brief?corridor={id}
 * 
 * Shows real source articles used, "insufficient signal" when no data exists,
 * and whether the brief was LLM-generated or auto-compiled.
 */
import { useState, useEffect } from 'react';
import { ENDPOINTS } from '../config';

const CORRIDOR_OPTIONS = [
  { id: 'hormuz',            label: 'Strait of Hormuz' },
  { id: 'red_sea',           label: 'Red Sea / Bab-el-Mandeb' },
  { id: 'suez',              label: 'Suez Canal' },
  { id: 'cape_of_good_hope', label: 'Cape of Good Hope' },
  { id: 'russia_route',      label: 'Russia / Black Sea' },
  { id: 'malacca',           label: 'Strait of Malacca' },
];

export default function CorridorBrief() {
  const [selected, setSelected] = useState('hormuz');
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);

  useEffect(() => {
    setLoading(true);
    setData(null);
    setError(null);
    fetch(`${ENDPOINTS.corridorBrief}?corridor=${selected}`)
      .then(r => r.json())
      .then(json => { setData(json); setLoading(false); })
      .catch(e => { setError(String(e)); setLoading(false); });
  }, [selected]);

  const articles     = data?.articles     || [];
  const brief        = data?.brief        || '';
  const llmStatus    = data?.llm_status   || '';
  const insufficient = llmStatus === 'insufficient_signal';

  const badgeColor = llmStatus === 'ok' ? '#3b82f6' :
                     llmStatus === 'fallback_no_key' ? '#f59e0b' : '#64748b';
  const badgeLabel = llmStatus === 'ok' ? 'Claude AI' :
                     llmStatus === 'fallback_no_key' ? 'Auto-compiled (no LLM key)' :
                     llmStatus === 'insufficient_signal' ? 'No recent data' : llmStatus;

  return (
    <div className="card">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
        <div className="card-title" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>📡</span> Intelligence Brief
        </div>
        <select
          value={selected}
          onChange={e => setSelected(e.target.value)}
          style={{
            background: 'var(--bg-overlay)',
            border: '1px solid var(--border)',
            borderRadius: 5, padding: '3px 8px',
            color: 'var(--text-primary)', fontSize: 11,
            cursor: 'pointer',
          }}
        >
          {CORRIDOR_OPTIONS.map(c => (
            <option key={c.id} value={c.id}>{c.label}</option>
          ))}
        </select>
      </div>

      {/* Description */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10, lineHeight: 1.5 }}>
        RAG-grounded synthesis of news articles from the last 48 hours for this corridor.
        The LLM only references the shown source articles — it does not invent information.
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--text-muted)', fontSize: 12 }}>
          <div style={{
            width: 14, height: 14, borderRadius: '50%',
            border: '2px solid var(--border)', borderTopColor: '#3b82f6',
            animation: 'spin 0.8s linear infinite',
            display: 'inline-block', marginRight: 8,
          }} />
          Loading brief…
        </div>
      )}

      {!loading && error && (
        <div style={{ color: '#ef4444', fontSize: 12, padding: '10px 0' }}>Error: {error}</div>
      )}

      {!loading && !error && (
        <>
          {/* Brief text */}
          <div style={{
            background: insufficient ? 'var(--bg-overlay)' : 'rgba(59,130,246,0.07)',
            border: `1px solid ${insufficient ? 'var(--border)' : 'rgba(59,130,246,0.2)'}`,
            borderRadius: 8, padding: '12px 14px', marginBottom: 10,
            lineHeight: 1.7, fontSize: 13,
            color: insufficient ? 'var(--text-muted)' : 'var(--text-primary)',
            fontStyle: insufficient ? 'italic' : 'normal',
          }}>
            {brief || 'No brief available.'}
          </div>

          {/* LLM status badge */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '0.06em',
              background: `${badgeColor}22`, color: badgeColor,
              border: `1px solid ${badgeColor}44`,
              padding: '2px 7px', borderRadius: 4,
            }}>
              {badgeLabel}
            </span>
            {articles.length > 0 && (
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                {articles.length} source article{articles.length !== 1 ? 's' : ''} used
              </span>
            )}
          </div>

          {/* Source articles */}
          {articles.length > 0 && (
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 600, marginBottom: 6, letterSpacing: '0.05em' }}>
                SOURCES RETRIEVED
              </div>
              {articles.map((art, i) => (
                <div key={i} style={{
                  borderLeft: '2px solid var(--border)',
                  paddingLeft: 10, marginBottom: 8, fontSize: 11,
                }}>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                    {art.link ? (
                      <a href={art.link} target="_blank" rel="noopener noreferrer"
                        style={{ color: 'var(--text-primary)', textDecoration: 'none' }}>
                        [{i + 1}] {art.title}
                      </a>
                    ) : `[${i + 1}] ${art.title}`}
                  </div>
                  <div style={{ color: 'var(--text-muted)', fontSize: 10 }}>
                    {art.source} · {art.date ? new Date(art.date).toLocaleDateString() : ''}
                  </div>
                  {art.key_takeaway && (
                    <div style={{ color: 'var(--text-secondary)', marginTop: 2, fontSize: 10 }}>
                      → {art.key_takeaway}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-footer)' }}>
        Source: macro_events_filtered.csv · 48h lookback · api/routers/corridor_brief.py
      </div>
    </div>
  );
}
