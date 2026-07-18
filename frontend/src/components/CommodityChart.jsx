// CommodityChart — Brent / WTI / USD-INR line chart using Recharts
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { useState } from 'react';

const TICKER_CONFIG = {
  'BZ=F':  { color: '#f59e0b', name: 'Brent ($/bbl)' },
  'CL=F':  { color: '#3b82f6', name: 'WTI ($/bbl)'   },
  'INR=X': { color: '#14b8a6', name: 'USD/INR'        },
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#111827', border: '1px solid #1f2d45',
      borderRadius: 8, padding: '8px 12px', fontSize: 12,
    }}>
      <div style={{ color: '#64748b', marginBottom: 4 }}>{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ color: p.color, fontVariantNumeric: 'tabular-nums' }}>
          {p.name}: <strong>{p.value?.toFixed(2) ?? '—'}</strong>
        </div>
      ))}
    </div>
  );
};

export default function CommodityChart({ data }) {
  const [hiddenTickers, setHiddenTickers] = useState(new Set());

  if (!data?.series?.length) {
    return <div style={{ color: '#64748b', fontSize: 12, padding: '1rem 0' }}>
      Awaiting commodity data… (run pipeline to populate)
    </div>;
  }

  // Merge series into a single array by date, keyed by ticker
  const dateMap = {};
  data.series.forEach(({ ticker, points }) => {
    points.forEach(p => {
      if (!dateMap[p.date]) dateMap[p.date] = { date: p.date };
      dateMap[p.date][ticker] = p.close;
    });
  });

  // Sort by date
  const chartData = Object.values(dateMap).sort((a, b) => a.date.localeCompare(b.date));

  const toggleTicker = (ticker) => {
    setHiddenTickers(prev => {
      const next = new Set(prev);
      next.has(ticker) ? next.delete(ticker) : next.add(ticker);
      return next;
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* Ticker toggle pills */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {data.series.map(({ ticker }) => {
          const cfg     = TICKER_CONFIG[ticker] || { color: '#94a3b8', name: ticker };
          const hidden  = hiddenTickers.has(ticker);
          return (
            <button
              key={ticker}
              onClick={() => toggleTicker(ticker)}
              style={{
                padding: '2px 10px', borderRadius: 999, fontSize: 11, cursor: 'pointer',
                border: `1px solid ${cfg.color}`,
                background: hidden ? 'transparent' : `${cfg.color}20`,
                color: hidden ? '#475569' : cfg.color,
                fontWeight: 600, transition: 'all 0.15s',
              }}
            >
              {cfg.name}
            </button>
          );
        })}
      </div>

      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={chartData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2d45" />
          <XAxis
            dataKey="date"
            tick={{ fill: '#475569', fontSize: 10 }}
            tickFormatter={d => d.slice(5)}  // MM-DD
            axisLine={false} tickLine={false}
          />
          <YAxis
            tick={{ fill: '#475569', fontSize: 10 }}
            axisLine={false} tickLine={false}
            width={42}
          />
          <Tooltip content={<CustomTooltip />} />
          {data.series.map(({ ticker }) => {
            const cfg = TICKER_CONFIG[ticker] || { color: '#94a3b8', name: ticker };
            if (hiddenTickers.has(ticker)) return null;
            return (
              <Line
                key={ticker}
                type="monotone"
                dataKey={ticker}
                name={cfg.name}
                stroke={cfg.color}
                dot={false}
                strokeWidth={2}
                connectNulls
              />
            );
          })}
        </LineChart>
      </ResponsiveContainer>

      <div style={{ fontSize: 10, color: '#334155' }}>
        Source: Yahoo Finance via yfinance · {data.as_of ? `as of ${data.as_of.slice(0, 10)}` : ''}
      </div>
    </div>
  );
}
