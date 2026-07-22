/**
 * App.jsx — India Energy Supply Chain Resilience Dashboard
 * PS2 Hackathon · Policy Decision Support
 *
 * Four modules, matching team ownership:
 *   MODULE 1 — RISK AGENT           (mine)   WorldMap, Riskometer, CorridorRiskBar, NewsFeed
 *   MODULE 2 — SCENARIO SIMULATOR   (team)   Fully functional simulator
 *   MODULE 3 — PROCUREMENT ENGINE   (team)   Fully functional Procurement Recommendation Engine
 *   MODULE 4 — RESERVE OPTIMIZER    (mine)   BufferStack + CommodityChart + SPRDrawdown
 *
 * Data: every panel polls its own endpoint every 60s.
 * No mock data — all numbers trace to live_macro_pipeline.py or cited config files.
 */

import { useState, useCallback, useEffect, lazy, Suspense } from 'react';
import { usePolling } from './hooks/usePolling';
import { useTheme }   from './hooks/useTheme';
import { ENDPOINTS, POLL_INTERVAL_MS } from './config';
import './index.css';

// Heavy components — lazy-loaded for fast initial paint
const WorldMap          = lazy(() => import('./components/WorldMap'));
const Riskometer        = lazy(() => import('./components/Riskometer'));
const BufferStack       = lazy(() => import('./components/BufferStack'));
const CommodityChart    = lazy(() => import('./components/CommodityChart'));
const NewsFeed          = lazy(() => import('./components/NewsFeed'));
const CorridorRiskBar   = lazy(() => import('./components/CorridorRiskBar'));
const ScenarioSimulator = lazy(() => import('./components/ScenarioSimulator'));
const ProcurementEngine = lazy(() => import('./components/ProcurementEngine'));
const SPRDrawdown       = lazy(() => import('./components/SPRDrawdown'));
const AutoAlerts        = lazy(() => import('./components/AutoAlerts'));
const CorridorBrief     = lazy(() => import('./components/CorridorBrief'));

// ─── Shared UI helpers ────────────────────────────────────────────────────────

function Card({ title, children, style = {}, headerRight, accent }) {
  return (
    <div className="card" style={{
      ...style,
      ...(accent ? { borderTop: `2px solid ${accent}` } : {}),
    }}>
      {title && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
          <div className="card-title" style={{ margin: 0 }}>{title}</div>
          {headerRight && <div>{headerRight}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

function LiveDot({ color = '#22c55e' }) {
  return (
    <span className="pulse-dot" style={{
      display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
      background: color, marginRight: 5,
    }} />
  );
}

function LoadingBox({ h = 120 }) {
  return (
    <div style={{
      height: h, borderRadius: 8, background: 'var(--bg-code)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      gap: 8,
    }}>
      <div style={{ width: 14, height: 14, borderRadius: '50%', border: '2px solid var(--border)', borderTopColor: '#3b82f6', animation: 'spin 0.8s linear infinite' }} />
      <span style={{ color: 'var(--text-footer)', fontSize: 11 }}>Loading…</span>
    </div>
  );
}

function ThemeToggle({ theme, onToggle }) {
  const isDark = theme === 'dark';
  return (
    <button className="theme-toggle" onClick={onToggle} aria-label="Toggle light/dark theme">
      <span>{isDark ? '☀️' : '🌙'}</span>
      <div className="toggle-track"><div className="toggle-knob" /></div>
      <span style={{ fontSize: 11 }}>{isDark ? 'Light' : 'Dark'}</span>
    </button>
  );
}

// ─── Main App ────────────────────────────────────────────────────────────────

export default function App() {
  const { theme, toggle: toggleTheme } = useTheme();

  // ── Navigation State & URL Hash Sync
  const getModuleFromHash = () => {
    const hash = window.location.hash.replace('#', '');
    const valid = ['risk-agent', 'scenario-simulator', 'procurement-engine', 'reserve-optimizer'];
    return valid.includes(hash) ? hash : 'risk-agent';
  };

  const [activeModule, setActiveModule] = useState(getModuleFromHash());

  useEffect(() => {
    const handleHashChange = () => {
      setActiveModule(getModuleFromHash());
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const switchTab = (mod) => {
    window.location.hash = mod;
    setActiveModule(mod);
  };

  // ── Data fetches (shared parent level so switching tabs doesn't cause refetches)
  const { data: riskData,  loading: riskLoading,  error: riskError,  lastUpdated } =
    usePolling(useCallback(() => fetch(ENDPOINTS.riskCorridors).then(r => r.json()), []), POLL_INTERVAL_MS);

  const { data: newsData,  loading: newsLoading } =
    usePolling(useCallback(() => fetch(`${ENDPOINTS.newsFeed}?limit=60&days=7`).then(r => r.json()), []), POLL_INTERVAL_MS);

  const { data: commodityData } =
    usePolling(useCallback(() => fetch(`${ENDPOINTS.commodityPrices}?days=30`).then(r => r.json()), []), POLL_INTERVAL_MS);

  const { data: bufferData, loading: bufferLoading } =
    usePolling(useCallback(() => fetch(ENDPOINTS.bufferStack).then(r => r.json()), []), POLL_INTERVAL_MS);

  const { data: healthData } =
    usePolling(useCallback(() => fetch(ENDPOINTS.health).then(r => r.json()), []), POLL_INTERVAL_MS);

  // LLM stats — carried in the news-feed response
  const { data: newsDataFull } =
    usePolling(useCallback(() => fetch(`${ENDPOINTS.newsFeed}?limit=1&days=7`).then(r => r.json()), []), POLL_INTERVAL_MS);
  const llmStats = newsDataFull?.llm_stats || null;

  // ── Derived state
  const corridors    = riskData?.corridors || [];
  const newsItems    = newsData?.items     || [];
  const scoredAt     = riskData?.as_of;
  const hasRiskData  = corridors.length > 0;
  const hasError     = Boolean(riskError);

  // Pipeline timestamp from health endpoint
  const lastCsvMtime = healthData?.last_csv_mtime;
  const pipelineTs   = lastCsvMtime
    ? new Date(lastCsvMtime).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : null;

  // ── News filters
  const [newsCorridorFilter, setNewsCorridorFilter] = useState('');
  const [newsCategoryFilter, setNewsCategoryFilter] = useState('energy_only');

  const filteredNews = newsItems.filter(item => {
    if (newsCorridorFilter && item.corridor !== newsCorridorFilter) return false;
    if (newsCategoryFilter === 'energy_only') {
      const energyCats = ["Shipping_Chokepoints", "India_Refinery_Ops", "India_SPR", "Alt_Crude_Sourcing", "Fuel_Substitution", "India_Fuel_Pricing", "Geopolitical", "Commodities"];
      if (!energyCats.includes(item.category)) return false;
    } else if (newsCategoryFilter && item.category !== newsCategoryFilter) {
      return false;
    }
    return true;
  });

  const selectStyle = {
    background: 'var(--bg-input)', border: '1px solid var(--border-input)',
    color: 'var(--text-primary)',  // was var(--text-input) — raised to match Scenario/Procurement dropdown contrast
    borderRadius: 6, padding: '3px 8px',
    fontSize: 11, cursor: 'pointer',
  };

  const TABS = [
    { id: 'risk-agent', label: 'Risk Agent' },
    { id: 'scenario-simulator', label: 'Scenario Simulator' },
    { id: 'procurement-engine', label: 'Procurement Engine' },
    { id: 'reserve-optimizer', label: 'Reserve Optimizer' },
  ];

  // ─── Layout ────────────────────────────────────────────────────────────────
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-base)', display: 'flex', flexDirection: 'column' }}>

      {/* ── Header ── */}
      <header style={{
        background: 'var(--bg-header)', borderBottom: '1px solid var(--border)',
        padding: '0 1.5rem', backdropFilter: 'var(--bg-header-blur)',
        position: 'sticky', top: 0, zIndex: 100,
      }}>
        <div style={{
          maxWidth: 1600, margin: '0 auto',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          height: 56, gap: 16,
        }}>
          {/* Brand */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
            <span style={{ fontSize: 20 }}>🛢️</span>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
                India Energy Resilience
              </div>
              <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                PS2 hackathon
              </div>
            </div>
          </div>

          {/* Navigation Bar */}
          <div style={{
            display: 'flex', gap: 4, background: 'var(--bg-overlay)',
            padding: 3, borderRadius: 8, border: '1px solid var(--border)'
          }}>
            {TABS.map(t => {
              const isActive = activeModule === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => switchTab(t.id)}
                  style={{
                    background: isActive ? 'var(--bg-card)' : 'transparent',
                    border: 'none',
                    color: isActive ? 'var(--text-primary)' : 'var(--text-muted)',
                    padding: '6px 14px',
                    borderRadius: 6,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'background 0.15s, color 0.15s',
                  }}
                >
                  {t.label}
                </button>
              );
            })}
          </div>

          {/* Right Section Info */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexShrink: 0, fontSize: 11 }}>
            <div style={{ display: 'flex', alignItems: 'center', color: hasError ? '#f59e0b' : '#22c55e' }}>
              <LiveDot color={hasError ? '#f59e0b' : '#22c55e'} />
              {hasError ? 'Feed Error' : 'All Feeds Live'}
            </div>

            <div style={{ color: 'var(--text-muted)' }}>
              {pipelineTs
                ? <>Pipeline: <strong style={{ color: 'var(--text-primary)' }}>{pipelineTs}</strong></>
                : <span style={{ color: '#334155' }}>Connecting…</span>
              }
            </div>

            <ThemeToggle theme={theme} onToggle={toggleTheme} />
          </div>
        </div>
      </header>

      {/* ── Main content area ── */}
      <main style={{ maxWidth: 1600, margin: '0 auto', padding: '1.25rem', width: '100%', flex: 1 }}>
        <Suspense fallback={<LoadingBox h={400} />}>

          {/* ── Tab 1: Risk Agent ── */}
          {activeModule === 'risk-agent' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '1rem' }}>
              {/* World Map */}
              <Card title="Global Shipping Corridors — Live Risk" accent="#ef4444">
                <div style={{ height: 540 }}>
                  <WorldMap
                    corridors={corridors}
                    pipelineTs={pipelineTs}
                    vesselEstimate={bufferData?.vessels_in_transit?.estimated_vessels}
                    vesselNote={bufferData?.vessels_in_transit?.note}
                  />
                </div>
              </Card>

              {/* Right column */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <Card title="Riskometer — Highest Risk Corridor">
                  {riskLoading && !hasRiskData
                    ? <LoadingBox h={180} />
                    : <Riskometer corridors={corridors} scoredAt={scoredAt} />
                  }
                </Card>

                <Card title="All Corridor Scores">
                  <CorridorRiskBar corridors={corridors} />
                </Card>
              </div>

              {/* Live Alerts panel (full width) */}
              <div style={{ gridColumn: '1 / -1' }}>
                <AutoAlerts />
              </div>

              {/* Intelligence Brief (full width) */}
              <div style={{ gridColumn: '1 / -1' }}>
                <CorridorBrief />
              </div>

              {/* Signal Validation stats row (only shown when LLM data available) */}
              {llmStats && llmStats.llm_available && (
                <div style={{ gridColumn: '1 / -1' }}>
                  <div style={{
                    background: 'var(--bg-overlay)',
                    border: '1px solid var(--border)',
                    borderRadius: 8, padding: '10px 16px',
                    display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap',
                  }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-primary)' }}>
                      🤖 LLM Signal Validation
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      <strong style={{ color: 'var(--text-primary)' }}>{llmStats.total_classified}</strong> events LLM-validated
                    </span>
                    <span style={{ fontSize: 11, color: llmStats.total_flagged > 0 ? '#f59e0b' : 'var(--text-muted)' }}>
                      <strong>{llmStats.total_flagged}</strong> flagged for review
                      {llmStats.total_flagged > 0 && ' ⚠️'}
                    </span>
                    <span style={{ fontSize: 10, color: 'var(--text-footer)', marginLeft: 'auto' }}>
                      Anthropic Claude · last 7 days
                    </span>
                  </div>
                </div>
              )}

              {/* News Feed (full width) */}
              <div style={{ gridColumn: '1 / -1', marginTop: '0.5rem' }}>
                <Card
                  title="Live Intelligence Feed"
                  headerRight={
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <select value={newsCorridorFilter} onChange={e => setNewsCorridorFilter(e.target.value)} style={selectStyle}>
                        <option value="">All corridors</option>
                        <option value="hormuz">Hormuz</option>
                        <option value="red_sea">Red Sea</option>
                        <option value="suez">Suez</option>
                        <option value="cape_of_good_hope">Cape of Good Hope</option>
                        <option value="russia_route">Russia Route</option>
                        <option value="malacca">Malacca</option>
                        <option value="india_domestic">India Domestic</option>
                        <option value="none">No corridor</option>
                      </select>
                      <select value={newsCategoryFilter} onChange={e => setNewsCategoryFilter(e.target.value)} style={selectStyle}>
                        <option value="energy_only">Energy Categories (Default)</option>
                        <option value="">All categories</option>
                        <option value="Shipping_Chokepoints">Shipping Chokepoints</option>
                        <option value="Geopolitical">Geopolitical</option>
                        <option value="Commodities">Commodities</option>
                        <option value="India_Refinery_Ops">India Refinery Ops</option>
                        <option value="India_SPR">India SPR</option>
                        <option value="Alt_Crude_Sourcing">Alt Crude Sourcing</option>
                        <option value="Fuel_Substitution">Fuel Substitution</option>
                        <option value="India_Fuel_Pricing">India Fuel Pricing</option>
                        <option value="India_Macro">India Macro</option>
                        <option value="India_Policy">India Policy</option>
                        <option value="US_Macro">US Macro</option>
                        <option value="RBI_Monetary">RBI Monetary</option>
                      </select>
                      <span style={{ fontSize: 11, color: 'var(--text-footer)' }}>{filteredNews.length} articles</span>
                    </div>
                  }
                >
                  <NewsFeed items={filteredNews} loading={newsLoading} pipelineTs={pipelineTs} />
                </Card>
              </div>
            </div>
          )}

          {/* ── Tab 2: Scenario Simulator ── */}
          {activeModule === 'scenario-simulator' && (
            <ScenarioSimulator corridors={corridors} />
          )}

          {/* ── Tab 3: Procurement Engine ── */}
          {activeModule === 'procurement-engine' && (
            <ProcurementEngine />
          )}

          {/* ── Tab 4: Reserve Optimizer (Restructured: Left 60%, Right 40%) ── */}
          {activeModule === 'reserve-optimizer' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 6fr) minmax(0, 4fr)', gap: '1rem', alignItems: 'start' }}>
              {/* Left column (60% width): SPR Drawdown Calculator + Commodity Prices chart below it */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <Card
                  title="SPR Drawdown Calculator"
                  accent="#8b5cf6"
                  headerRight={
                    <span style={{ fontSize: 10, color: 'var(--text-footer)' }}>
                      PIB · ISPRL · PPAC sources
                    </span>
                  }
                >
                  <SPRDrawdown bufferData={bufferData} />
                </Card>

                <Card title="Commodity Prices — Brent · WTI · USD/INR">
                  <CommodityChart data={commodityData} />
                </Card>
              </div>

              {/* Right column (40% width): National Buffer Stack */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <Card
                  title="National Buffer Stack"
                  headerRight={
                    <span style={{ fontSize: 10, color: 'var(--text-footer)' }}>PIB + PPAC sources</span>
                  }
                >
                  <BufferStack data={bufferData} loading={bufferLoading} />
                </Card>
              </div>
            </div>
          )}

        </Suspense>
      </main>

      {/* ── Footer ── */}
      <footer style={{
        borderTop: '1px solid var(--border)', padding: '0.75rem 1.5rem',
        background: 'var(--bg-footer)', fontSize: 10, color: 'var(--text-footer)',
        display: 'flex', justifyContent: 'space-between',
      }}>
        <span>
          PS2 Hackathon · AI-Driven Energy Supply Chain Resilience for India ·
          Data: PPAC · PIB · OFAC · EIA · IEA · Yahoo Finance · Google News RSS
        </span>
        <span>
          All figures timestamped — verify SPR fill % and on-water days against ISPRL/PPAC before policy decisions
        </span>
      </footer>
    </div>
  );
}
