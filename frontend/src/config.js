// Central API config — all endpoints in one place
export const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export const ENDPOINTS = {
  riskCorridors:    `${API_BASE}/api/risk-corridors`,
  newsFeed:         `${API_BASE}/api/news-feed`,
  commodityPrices:  `${API_BASE}/api/commodity-prices`,
  sanctions:        `${API_BASE}/api/sanctions/recent`,
  bufferStack:      `${API_BASE}/api/buffer-stack`,
  bufferCoverage:   `${API_BASE}/api/buffer-coverage`,
  scenarioSimulate: `${API_BASE}/api/scenario-simulate`,
  procurementRecommend: `${API_BASE}/api/procurement-recommend`,
  autoAlerts:       `${API_BASE}/api/auto-alerts`,
  corridorBrief:    `${API_BASE}/api/corridor-brief`,
  health:           `${API_BASE}/api/health`,
  base:             API_BASE,
};

// Poll interval: 60 seconds
export const POLL_INTERVAL_MS = 60_000;
