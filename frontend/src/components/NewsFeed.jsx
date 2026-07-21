// NewsFeed — scrollable list of recent news items with relative timestamps
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { CORRIDOR_LABELS, LEVEL_COLORS } from '../utils/corridors';

dayjs.extend(relativeTime);

const SEVERITY_COLORS = ['#475569','#64748b','#3b82f6','#f59e0b','#f97316','#ef4444'];

export default function NewsFeed({ items = [], loading }) {
  if (loading && !items.length) {
    return (
      <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '1rem 0' }}>
        Loading news feed…
      </div>
    );
  }

  if (!items.length) {
    return (
      <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '1rem 0' }}>
        No articles in this window. Run live_macro_pipeline.py to populate.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 1, maxHeight: 380, overflowY: 'auto' }}>
      {items.map((item, idx) => {
        const level   = item.severity >= 4 ? 'red' : item.severity >= 2 ? 'amber' : 'green';
        const sevColor = SEVERITY_COLORS[Math.min(item.severity, 5)];
        const relTime  = dayjs(item.date).fromNow();
        const corridor = CORRIDOR_LABELS[item.corridor] || null;

        return (
          <a
            key={idx}
            href={item.link || '#'}
            target="_blank"
            rel="noopener noreferrer"
            className="fade-in"
            style={{
              display: 'block', padding: '10px 12px',
              borderRadius: 8, textDecoration: 'none', color: 'inherit',
              borderLeft: `3px solid ${sevColor}`,
              background: 'var(--bg-overlay)',
              marginBottom: 2,
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-overlay-hov)'}
            onMouseLeave={e => e.currentTarget.style.background = 'var(--bg-overlay)'}
          >
            {/* Top row: source + time */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {item.source || 'Unknown'}
              </span>
              <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>{relTime}</span>
            </div>

            {/* Title */}
            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', lineHeight: 1.4, marginBottom: 4 }}>
              {item.title}
            </div>

            {/* Takeaway (if available) */}
            {item.key_takeaway && (
              <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 5, lineHeight: 1.4 }}>
                {item.key_takeaway.slice(0, 120)}{item.key_takeaway.length > 120 ? '…' : ''}
              </div>
            )}

            {/* Tags */}
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              <span className="badge badge-gray">{item.category}</span>
              {corridor && <span className={`badge badge-${level}`}>{corridor}</span>}
              {item.severity > 0 && (
                <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 999,
                  background: `${sevColor}20`, color: sevColor, border: `1px solid ${sevColor}`,
                  fontWeight: 700, letterSpacing: '0.04em' }}>
                  SEV {item.severity}
                </span>
              )}
            </div>
          </a>
        );
      })}
    </div>
  );
}
