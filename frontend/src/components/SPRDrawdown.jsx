// SPRDrawdown — Reserve Optimizer Module (PS2 Module 4)
// Deterministic SPR drawdown calculator using live /api/buffer-coverage backend endpoint.
import { useState, useEffect } from 'react';
import { API_BASE } from '../config';

function ResultRow({ label, value, unit, color, note, citation }) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr auto',
      alignItems: 'start', gap: 8,
      padding: '10px 12px', borderRadius: 8,
      background: 'var(--bg-overlay)',
      border: `1px solid ${color}30`,
    }}>
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{label}</div>
        {note && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{note}</div>}
        {citation && <div style={{ fontSize: 10, color: '#334155', marginTop: 2 }}>Source: {citation}</div>}
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <span style={{ fontSize: 20, fontWeight: 700, color, fontVariantNumeric: 'tabular-nums' }}>
          {value}
        </span>
        {unit && <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 3 }}>{unit}</span>}
      </div>
    </div>
  );
}

export default function SPRDrawdown({ bufferData }) {
  const [gapPct, setGapPct]           = useState('');
  const [durationDays, setDurationDays] = useState('');
  const [coverageData, setCoverageData] = useState(null);
  const [loading, setLoading]         = useState(false);

  // Extract static config info for citation & site data
  const sprLayer      = bufferData?.layers?.find(l => l.layer === 'spr');
  const refineryLayer = bufferData?.layers?.find(l => l.layer === 'refinery_stock');

  const sprDays      = sprLayer?.days_cover ?? null;
  const refineryDays = refineryLayer?.days_cover ?? null;
  const sprFillPct   = sprLayer?.current_fill_pct ?? null;

  const gap  = parseFloat(gapPct);
  const dur  = parseFloat(durationDays);
  const hasInputs   = gap > 0 && gap <= 100;
  const hasBufferData = sprDays != null && refineryDays != null;

  // Sync to backend coverage endpoint
  useEffect(() => {
    if (!hasInputs) {
      setCoverageData(null);
      return;
    }
    const controller = new AbortController();
    const fetchCoverage = async () => {
      setLoading(true);
      try {
        const url = `${API_BASE}/api/buffer-coverage?gap_pct=${gap}&duration_days=${dur || 0}`;
        const res = await fetch(url, { signal: controller.signal });
        const json = await res.json();
        setCoverageData(json);
      } catch (e) {
        if (e.name !== 'AbortError') {
          console.error(e);
        }
      } finally {
        setLoading(false);
      }
    };
    fetchCoverage();
    return () => controller.abort();
  }, [gap, dur, hasInputs]);

  const statusColor = (sufficient) =>
    sufficient === true ? '#22c55e' : sufficient === false ? '#ef4444' : '#64748b';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Data inputs from API */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr',
        gap: 8, padding: '10px 12px', borderRadius: 8,
        background: 'rgba(139,92,246,0.06)', border: '1px solid rgba(139,92,246,0.2)',
      }}>
        <div>
          <div style={{ fontSize: 10, color: '#8b5cf6', textTransform: 'uppercase', letterSpacing: '0.06em' }}>SPR Days Cover</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#c4b5fd', fontVariantNumeric: 'tabular-nums' }}>
            {sprDays != null ? `${sprDays}d` : '—'}
          </div>
          <div style={{ fontSize: 10, color: '#475569' }}>
            {sprFillPct != null ? `${sprFillPct}% fill · ` : ''}PIB + RTI, Mar 2026
          </div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: '#14b8a6', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Refinery Stock</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#5eead4', fontVariantNumeric: 'tabular-nums' }}>
            {refineryDays != null ? `${refineryDays}d` : '—'}
          </div>
          <div style={{ fontSize: 10, color: '#475569' }}>PIB press release, Mar 2026</div>
        </div>
      </div>

      {/* User inputs */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
            Supply gap (% of daily demand)
          </label>
          <input
            type="number" min="1" max="100" step="1"
            value={gapPct}
            onChange={e => setGapPct(e.target.value)}
            placeholder="e.g. 20"
            style={{
              width: '100%', background: 'var(--bg-input)',
              border: '1px solid var(--border-input)', color: 'var(--text-input)',
              borderRadius: 6, padding: '7px 10px', fontSize: 13,
              fontVariantNumeric: 'tabular-nums', boxSizing: 'border-box',
            }}
          />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
            Disruption duration (days)
          </label>
          <input
            type="number" min="1" max="365" step="1"
            value={durationDays}
            onChange={e => setDurationDays(e.target.value)}
            placeholder="e.g. 30"
            style={{
              width: '100%', background: 'var(--bg-input)',
              border: '1px solid var(--border-input)', color: 'var(--text-input)',
              borderRadius: 6, padding: '7px 10px', fontSize: 13,
              fontVariantNumeric: 'tabular-nums', boxSizing: 'border-box',
            }}
          />
        </div>
      </div>

      {/* Headline Pass/Fail Result */}
      {hasInputs && coverageData && (
        <div style={{
          padding: '12px 14px', borderRadius: 8,
          background: coverageData.total_sufficient ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
          border: `1px solid ${coverageData.total_sufficient ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}`,
        }}>
          <div style={{
            fontSize: 13, fontWeight: 700,
            color: coverageData.total_sufficient ? '#22c55e' : '#ef4444',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <span>{coverageData.total_sufficient ? '✓' : '✗'}</span>
            <span>{coverageData.total_sufficient ? 'RESERVES SUFFICIENT' : 'RESERVES INSUFFICIENT'}</span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-primary)', marginTop: 4, lineHeight: 1.4 }}>
            {coverageData.total_sufficient ? (
              <>
                Combined reserves cover this scenario for <strong>{coverageData.total_cover_days} days</strong>{' '}
                ({coverageData.total_difference_days > 0 ? `with ${coverageData.total_difference_days} days to spare` : 'matching exactly'}).
              </>
            ) : (
              <>
                Reserves will be fully exhausted in <strong>{coverageData.total_cover_days} days</strong>.{' '}
                Combined buffer <span style={{ color: '#ef4444', fontWeight: 600 }}>falls short by {Math.abs(coverageData.total_difference_days)} days</span>.
              </>
            )}
          </div>
        </div>
      )}

      {/* Results details */}
      {hasInputs && coverageData ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <ResultRow
            label="SPR alone covers gap for"
            value={coverageData.spr_cover_days.toFixed(1)}
            unit="days"
            color={statusColor(coverageData.spr_sufficient)}
            note={dur > 0
              ? coverageData.spr_sufficient
                ? `✓ Sufficient for ${dur}-day disruption`
                : `✗ Exhausted ${Math.abs(coverageData.spr_difference_days).toFixed(1)} days before disruption ends`
              : undefined
            }
            citation="SPR: PIB PRID=1694712 + Rajya Sabha RTI, 23 Mar 2026"
          />
          <ResultRow
            label="SPR + Refinery stock covers"
            value={coverageData.total_cover_days.toFixed(1)}
            unit="days"
            color={statusColor(coverageData.total_sufficient)}
            note={dur > 0
              ? coverageData.total_sufficient
                ? `✓ Combined buffer sufficient for ${dur}-day disruption`
                : `✗ Combined buffer fails ${Math.abs(coverageData.total_difference_days).toFixed(1)} days short`
              : undefined
            }
            citation="Refinery stock: PIB PRID=1694712, 23 Mar 2026"
          />
        </div>
      ) : hasInputs && !coverageData && loading ? (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '8px 0', display: 'flex', gap: 6, alignItems: 'center' }}>
          <div style={{ width: 12, height: 12, borderRadius: '50%', border: '2px solid var(--border)', borderTopColor: '#3b82f6', animation: 'spin 0.8s linear infinite' }} />
          Calculating coverage...
        </div>
      ) : hasInputs && !hasBufferData ? (
        <div style={{ fontSize: 12, color: '#f59e0b', padding: '8px 0' }}>
          ⚠ Buffer data not yet loaded — ensure API is running and buffer_config.json is present.
        </div>
      ) : (
        <div style={{ fontSize: 11, color: '#334155', padding: '6px 0' }}>
          Enter a supply gap % above to compute drawdown coverage.
        </div>
      )}

      {/* Formula caption — visible, auditable */}
      <div style={{
        fontSize: 10, color: '#334155', lineHeight: 1.7,
        background: 'rgba(255,255,255,0.02)', borderRadius: 6,
        padding: '8px 10px', border: '1px solid #1f2d45',
        fontFamily: 'monospace',
      }}>
        spr_cover   = spr_days / (gap_pct / 100)<br />
        total_cover = (spr_days + refinery_days) / (gap_pct / 100)<br />
        <span style={{ color: '#475569' }}>
          Calculations are done via shared backend logic. Consumption cancels algebraically.
        </span>
      </div>

      {/* Caveat */}
      <div style={{ fontSize: 10, color: '#334155', lineHeight: 1.5 }}>
        ⚠ SPR fill % is dynamic (last cited: {sprFillPct ?? '?'}%, Mar 2026) — verify against ISPRL/PPAC disclosures before policy decisions.
      </div>
    </div>
  );
}
