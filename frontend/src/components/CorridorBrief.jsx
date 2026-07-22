/**
 * CorridorBrief.jsx
 *
 * RAG-grounded 2-3 sentence intelligence brief for a selected corridor.
 * Calls GET /api/corridor-brief?corridor={id}
 *
 * Shows real source articles used, "insufficient signal" when no data exists,
 * and the LLM status (which now includes the 4-key round-robin pool health).
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

// ── Status badge config ────────────────────────────────────────────────────
const STATUS_META = {
  ok:                       { color: '#3b82f6', label: 'Gemini AI · Live' },
  fallback_no_key:          { color: '#f59e0b', label: 'Auto-compiled (no API key)' },
  fallback_all_keys_failed: { color: '#ef4444', label: 'All keys exhausted — auto-compiled' },
  insufficient_signal:      { color: '#64748b', label: 'No recent data' },
};

function StatusBadge({ status, keysInPool }) {
  const meta   = STATUS_META[status] || { color: '#64748b', label: status };
  const isOk   = status === 'ok';
  const isFail = status === 'fallback_all_keys_failed';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
      {/* Primary status badge */}
      <span style={{
        fontSize: 9, fontWeight: 700, letterSpacing: '0.06em',
        background: `${meta.color}22`, color: meta.color,
        border: `1px solid ${meta.color}44`,
        padding: '2px 7px', borderRadius: 4,
        display: 'inline-flex', alignItems: 'center', gap: 4,
      }}>
        {isOk  && <span style={{ fontSize: 8 }}>●</span>}
        {isFail && <span style={{ fontSize: 8 }}>⚠</span>}
        {meta.label}
      </span>

      {/* Key pool indicator — only shown when we know the count */}
      {keysInPool != null && keysInPool > 0 && (
        <span style={{
          fontSize: 9, color: '#475569',
          display: 'inline-flex', alignItems: 'center', gap: 3,
        }}>
          <span style={{ color: isOk ? '#22c55e' : '#64748b' }}>⬡</span>
          {keysInPool} key{keysInPool !== 1 ? 's' : ''} in pool
        </span>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────
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

  const articles    = data?.articles     || [];
  const brief       = data?.brief        || '';
  const llmStatus   = data?.llm_status   || '';
  const keysInPool  = data?.keys_in_pool ?? null;
  const insufficient = llmStatus === 'insufficient_signal';

  return (
    <div className="card">
      {/* ── Header ── */}
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

      {/* ── Description ── */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10, lineHeight: 1.5 }}>
        RAG-grounded synthesis of news articles from the last 48 hours for this corridor.
        The LLM only references the shown source articles — it does not invent information.
        {keysInPool != null && (
          <span style={{ color: keysInPool >= 2 ? '#22c55e' : keysInPool === 1 ? '#f59e0b' : '#ef4444', marginLeft: 6, fontWeight: 600 }}>
            {keysInPool >= 2
              ? `${keysInPool}-key pool active.`
              : keysInPool === 1
              ? '1 key active (add more to GEMINI_API_KEY_1..4 for resilience).'
              : 'No keys loaded — running in auto-compile mode.'}
          </span>
        )}
      </div>

      {/* ── Loading ── */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--text-muted)', fontSize: 12 }}>
          <div style={{
            width: 14, height: 14, borderRadius: '50%',
            border: '2px solid var(--border)', borderTopColor: '#3b82f6',
            animation: 'spin 0.8s linear infinite',
            display: 'inline-block', marginRight: 8,
          }} />
          Calling Gemini (round-robin key pool)…
        </div>
      )}

      {/* ── Error ── */}
      {!loading && error && (
        <div style={{ color: '#ef4444', fontSize: 12, padding: '10px 0' }}>Error: {error}</div>
      )}

      {/* ── Content ── */}
      {!loading && !error && (
        <>
          {/* Brief text box */}
          <div style={{
            background: insufficient ? 'var(--bg-overlay)' : 'rgba(59,130,246,0.06)',
            border: `1px solid ${insufficient ? 'var(--border)' : 'rgba(59,130,246,0.25)'}`,
            borderRadius: 8, padding: '14px 16px', marginBottom: 14,
          }}>
            <div style={{
              fontSize: 10, fontWeight: 700, letterSpacing: '0.06em',
              color: insufficient ? 'var(--text-muted)' : '#3b82f6',
              textTransform: 'uppercase', marginBottom: 6,
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <span>📝</span> SYNTHESIZED NARRATIVE BRIEF
            </div>
            <div style={{
              lineHeight: 1.6, fontSize: 14, fontWeight: 400,
              color: insufficient ? 'var(--text-muted)' : 'var(--text-primary)',
              fontStyle: insufficient ? 'italic' : 'normal',
            }}>
              {brief || 'No brief available.'}
            </div>
          </div>

          {/* LLM status + key pool indicator */}
          <div style={{ marginBottom: 16 }}>
            <StatusBadge status={llmStatus} keysInPool={keysInPool} />
            {articles.length > 0 && (
              <span style={{ fontSize: 10, color: 'var(--text-muted)', display: 'block', marginTop: 4 }}>
                {articles.length} source article{articles.length !== 1 ? 's' : ''} retrieved & synthesized
              </span>
            )}
          </div>

          {/* Source articles — visually separated section */}
          {articles.length > 0 && (
            <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 700, marginBottom: 8, letterSpacing: '0.06em' }}>
                SOURCES RETRIEVED ({articles.length})
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

      {/* ── Footer ── */}
      <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-footer)' }}>
        Source: macro_events_filtered.csv · 48h lookback · Gemini 2.0 Flash · round-robin key pool
      </div>
    </div>
  );
}
