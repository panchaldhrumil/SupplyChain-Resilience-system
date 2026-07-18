# 🛢️ India Energy Supply Chain Resilience Dashboard
### PS2 Hackathon — AI-Driven Energy Supply Chain Resilience for Import-Dependent Economies

A real-data, end-to-end intelligence dashboard for Indian **policy-makers and bureaucrats** to monitor crude oil supply chain risk — shipping corridors, national buffer stocks, commodity prices, sanctions, and live geopolitical news — all in one dark (or light) interface.

---

## 📁 Project Structure

```
Project/
├── backend/
│   ├── live_macro_pipeline.py        ← Core data pipeline (scraper + enricher)
│   ├── config/
│   │   ├── buffer_config.json        ← SPR & refinery stock (real cited values)
│   │   └── import_mix.json           ← Crude import-mix template (fill from PPAC)
│   └── api/
│       ├── main.py                   ← FastAPI app entry point
│       └── routers/
│           ├── risk_corridors.py     ← GET /api/risk-corridors
│           ├── news_feed.py          ← GET /api/news-feed
│           ├── commodity_prices.py   ← GET /api/commodity-prices
│           ├── sanctions.py          ← GET /api/sanctions/recent
│           └── buffer_stack.py       ← GET /api/buffer-stack
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx                   ← Full dashboard layout
│       ├── index.css                 ← Design tokens (dark + light themes)
│       ├── config.js                 ← API endpoint URLs + poll interval
│       ├── hooks/
│       │   ├── usePolling.js         ← 60-second polling hook
│       │   └── useTheme.js           ← Light/dark theme toggle + localStorage
│       ├── utils/
│       │   └── corridors.js          ← Corridor labels, colors, Leaflet paths
│       └── components/
│           ├── WorldMap.jsx          ← Leaflet map with corridor polylines
│           ├── Riskometer.jsx        ← SVG arc gauge (highest-risk corridor)
│           ├── CorridorRiskBar.jsx   ← Mini score bars for all corridors
│           ├── BufferStack.jsx       ← Stacked buffer bar + PIB citations
│           ├── CommodityChart.jsx    ← Recharts line chart (Brent/WTI/INR)
│           ├── NewsFeed.jsx          ← Filterable news list with timestamps
│           └── PlaceholderCard.jsx   ← "Coming soon" shells
└── requirements.txt                  ← Python dependencies
```

---

## 🚀 How to Run (Step-by-Step)

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- All Python packages installed (see [Dependencies](#dependencies))

---

### Step 1 — Install Python dependencies
```bash
pip install -r requirements.txt
```

### Step 2 — Run the data pipeline
This scrapes real news (Google News RSS + official govt RSS feeds), enriches articles, and writes CSVs that the API reads from.

```bash
cd "c:\Users\DELL\Desktop\ET gen AI Hackthon\Project\backend"

python live_macro_pipeline.py \
  --from-date 2026-07-10 \
  --to-date 2026-07-17 \
  --no-db \
  --no-enrich
```

> **Tip:** Remove `--no-enrich` to enable full article text enrichment (slower). Remove `--no-db` only if you have a Postgres instance configured.

Output CSVs are written to `D:\StockData\MACRO_EVENTS\` by default. Override with:
```bash
$env:CSV_OUTPUT_DIR = "C:\YourCustomPath"
python live_macro_pipeline.py ...
```

### Step 3 — Start the FastAPI backend
```bash
cd "c:\Users\DELL\Desktop\ET gen AI Hackthon\Project\backend"
uvicorn api.main:app --reload --port 8000
```

Verify it's running:
- Health check: http://localhost:8000/api/health
- API docs (auto-generated): http://localhost:8000/docs

### Step 4 — Start the React frontend
```bash
cd "c:\Users\DELL\Desktop\ET gen AI Hackthon\Project\frontend"
npm install        # only first time
npm run dev
```

Open: **http://localhost:5173**

---

## 🧠 What Each Part Does

### 1. `live_macro_pipeline.py` — The Data Brain

The core scraping and enrichment engine. Runs as a one-shot script (no internal loop) — designed to be triggered by a scheduler every 15–30 minutes.

**Flow:**
```
fetch_query()           ← Google News RSS per MACRO_QUERY tuple
fetch_official_rss()    ← Govt RSS feeds (RBI, PIB, SEBI, Fed, MOSPI…)
  ↓ apply_corridor_impact()   ← Tags each item with corridor + buffer_layer + severity
cross-query dedup       ← Removes duplicate URLs seen across multiple queries
_deduplicate_day_group()← Jaccard similarity clustering (keeps highest-priority source)
_is_relevant()          ← Broad keyword gate (drops off-topic items)
enrich_dataframe()      ← Fetches full article text + extracts numbers + key takeaway
write CSVs              ← macro_events_filtered.csv, commodity_prices.csv, etc.
upsert_macro_events()   ← Optional Postgres upsert (skipped with --no-db)
```

**Key configuration constants in the file:**

| Constant | Purpose |
|---|---|
| `MACRO_QUERIES` | `(category, search_query)` tuples — 12 categories, 6–10 queries each |
| `IMPACT_MAP` | Keywords → `(affected_sectors, affected_companies)` mapping |
| `CORRIDOR_IMPACT_MAP` | Keywords → `{buffer_layer, corridor, severity}` mapping |
| `OFFICIAL_RSS_FEEDS` | Direct RSS feeds for RBI, PIB, SEBI, Fed, MOSPI, IMF, World Bank |
| `DEFAULT_OUTPUT_DIR` | Where CSVs are written (`D:\StockData\MACRO_EVENTS`) |
| `SIMILARITY_THRESHOLD` | Jaccard dedup threshold (default `0.48`) |

**Categories scraped:**

| Category | What it covers |
|---|---|
| `Shipping_Chokepoints` | Hormuz, Bab-el-Mandeb, Suez, Cape, Malacca, Panama, Red Sea |
| `India_Refinery_Ops` | IOC, BPCL, HPCL, Reliance Jamnagar throughput & shutdowns |
| `India_SPR` | Strategic Petroleum Reserve releases & capacity |
| `Alt_Crude_Sourcing` | Russia discount crude, US WTI, West Africa, Brazil diversification |
| `Fuel_Substitution` | LNG, CNG, EV, solar, ethanol blending policy |
| `India_Fuel_Pricing` | Petrol/diesel retail price, LPG pricing, subsidy policy |
| `Geopolitical` | Hormuz, OPEC+, Russia, Taiwan, Middle East escalation |
| `Commodities` | Brent, WTI, LNG, LME metals, Baltic Dry Index |
| `India_Macro` | CPI, GDP, IIP, current account, rupee |
| `India_Policy` | MoPNG, PPAC, petroleum ministry policy |
| `US_Macro` | FOMC, Fed speeches, US jobs/CPI |
| `RBI_Monetary` | Repo rate, MPC minutes, liquidity |

**Corridor impact tagging** — every scraped item is tagged with:
- `buffer_layer`: `"on_water"` | `"refinery_stock"` | `"spr"` | `"none"`
- `corridor`: `"hormuz"` | `"red_sea"` | `"suez"` | `"cape_of_good_hope"` | `"russia_route"` | `"malacca"` | `"india_domestic"` | `"none"`
- `severity`: `0–5` integer (0 = no risk signal, 5 = critical)

---

### 2. `backend/api/` — FastAPI REST Layer

No Postgres required — every endpoint reads directly from the CSVs that `live_macro_pipeline.py` writes.

**Environment variables:**

| Variable | Default | Purpose |
|---|---|---|
| `CSV_OUTPUT_DIR` | `D:\StockData\MACRO_EVENTS` | Where pipeline CSVs live |
| `CONFIG_DIR` | `backend/config/` | Where buffer_config.json lives |

#### Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Liveness check + config paths |
| `/api/risk-corridors` | GET | Corridor risk scores (exponential recency decay) |
| `/api/news-feed` | GET | Filtered news items from macro_events_filtered.csv |
| `/api/commodity-prices` | GET | Brent, WTI, USD/INR from commodity_prices.csv |
| `/api/sanctions/recent` | GET | New OFAC SDN designations since last run |
| `/api/buffer-stack` | GET | SPR + refinery stock + on-water days estimate |



**Corridor risk scoring** (`risk_corridors.py`):
- Reads `macro_events_filtered.csv`
- For each event, weight = `severity × e^(−λt)` where `λ = ln(2) / 36` hours (half-life = 36h)
- Scores normalized to 0–100; thresholds: red ≥ 60, amber ≥ 25, green < 25
<!--  explanation :
 1. Risk decay: weight = severity × e^(−λt), λ = ln(2)/36
This is exponential half-life decay applied to news events. severity (1–5) is the base importance of an article from CORRIDOR_IMPACT_MAP. t is hours since publication. e^(−λt) shrinks that severity over time, and because λ = ln(2)/36, the weight is mathematically guaranteed to drop to exactly half every 36 hours — a fresh Hormuz-attack article counts at full severity right now, half as much 36 hours later, a quarter after 72 hours, and so on, smoothly, not as a hard cutoff.
Why this matters for your dashboard: without decay, a "Hormuz blockade" headline from last Tuesday would count exactly as much as one from this morning, so once something bad enters your 7-day window, your Riskometer would stay pinned at "critical" for a full week even if the crisis resolved in a day. The decay makes the score behave like a live pulse — it spikes the moment real news breaks and cools down organically as coverage fades, which is exactly the "weather app for oil disruption" framing from your blueprint. 36 hours specifically is a reasonable middle ground: short enough that yesterday's news doesn't dominate forever, long enough that one quiet news cycle doesn't erase a real ongoing crisis. -->



**Buffer stack** (`buffer_stack.py`):

| Layer | Value | Source |
|---|---|---|
| SPR | **6.1 days** (at 64% fill) | PIB press release + Rajya Sabha RTI, 23 Mar 2026 |
| Refinery stock | **64.5 days** | PIB press release, 23 Mar 2026 |
| On-water | Calculated (see below) | Derived from PPAC import mix |



**`calculate_on_water_days()` methodology:**
```
weighted_avg_transit_days = Σ (import_share_i / 100) × transit_days_i
days_cover = weighted_avg_transit_days
             (consumption terms cancel algebraically)
```
> Always displayed with `methodology: "estimated"` badge — never labelled "live" or "real-time".
> Fill `backend/config/import_mix.json` with PPAC Monthly Import Data to activate this calculation.
<!-- Explanation :
2. On-water days: weighted_avg_transit_days = Σ (share_i/100) × transit_days_i
The logic here is a simplified version of Little's Law (a standard result from queueing theory: inventory in a pipeline = throughput rate × time spent in the pipeline). At steady state, the number of barrels currently "in transit" toward India equals your daily import rate multiplied by average voyage time. When you then ask "how many days of consumption does that represent," and your import rate roughly equals your consumption rate (which is close to true since India imports ~88% of what it consumes), the consumption term cancels out algebraically — so the answer collapses to just the import-share-weighted average of transit times per route. That's a legitimate mathematical simplification, not hand-waving, but it's explicitly a steady-state approximation: it assumes normal, undisrupted flow, so it will be systematically wrong during the exact crisis moment you're trying to model (which is honest, and is why it's flagged "estimated," never "live"). -->

---

### 3. `frontend/` — React Dashboard

Built with **Vite + React + Tailwind CSS v4**.

**Data strategy:** Each panel uses the `usePolling` hook to fetch its endpoint independently every **60 seconds**. No WebSockets — simple polling was chosen for MVP reliability.

**Theme:** Supports **dark mode** (default) and **light mode**. Toggle in header. Persists to `localStorage`. Respects system `prefers-color-scheme` as first-load default.

#### Components

| Component | What it shows |
|---|---|
| `WorldMap` | Leaflet map (dark CARTO tiles). Corridor polylines colored red/amber/green by risk level. Click for score + top headline tooltip. |
| `Riskometer` | SVG arc gauge showing the score (0–100) of the single highest-risk corridor. |
| `CorridorRiskBar` | Horizontal mini progress bars for all corridors, sorted by score. |
| `BufferStack` | Stacked bar: on_water + refinery_stock + SPR days. Click any layer to reveal PIB/PPAC source citation. Estimated layers show ⚠ badge. |
| `CommodityChart` | Recharts line chart for Brent ($/bbl), WTI ($/bbl), USD/INR. Toggle individual series. 30-day window. |
| `NewsFeed` | Scrollable article list with dayjs relative timestamps, severity color bar, corridor tags. Filter by corridor and/or category. |
| `PlaceholderCard` | Shells for future modules: Scenario Simulator, Procurement Engine, Decision Meter. |

---

## ⚙️ Configuration Files

### `backend/config/buffer_config.json`
Holds real cited values for SPR and refinery stock. **Do not change numeric values without updating the `source` citation field.**

```jsonc
{
  "spr": {
    "total_capacity_mmt": 5.33,           // Visakhapatnam + Mangaluru + Padur
    "current_fill_pct": 64,               // Dynamic — re-verify before demo
    "estimated_days_cover_current": 6.1,  // At 64% fill
    "days_cover_at_full_capacity": 9.5,
    "source": "PIB PRID=1694712 + Rajya Sabha RTI, 23 Mar 2026"
  },
  "refinery_stock": {
    "days_cover": 64.5,                   // Aggregate product stocks at refineries+depots
    "source": "PIB PRID=1694712, 23 Mar 2026"
  }
}
```

### `backend/config/import_mix.json`
**Template — you must fill this from PPAC data before the on-water calculation activates.**

Required fields per source country:
- `import_share_pct` — from PPAC Monthly Import Data (ppac.gov.in)
- `transit_days_typical` — typical voyage days to Indian west coast port

Also set `daily_consumption_bbl` from PPAC Daily Petroleum Report.

### `frontend/src/config.js`
```js
export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const POLL_INTERVAL_MS = 60_000;  // 60 seconds
```
Set `VITE_API_URL` in a `.env` file to point at a deployed backend.

---

## 🔗 Data Sources

| Data | Source | How fetched |
|---|---|---|
| News & geopolitical events | Google News RSS + official govt RSS feeds | `live_macro_pipeline.py` |
| RBI policy | `rbi.org.in/RSS/RSSFeed.aspx` | `fetch_official_rss()` |
| PIB / Ministry of Finance | `pib.gov.in`, `finmin.nic.in` | `fetch_official_rss()` |
| MOSPI (GDP/IIP/CPI) | `mospi.gov.in/rss.xml` | `fetch_official_rss()` |
| US Federal Reserve | `federalreserve.gov/feeds/` | `fetch_official_rss()` |
| OFAC SDN sanctions | `ofac.treas.gov` (CSV download) | `fetch_ofac_sanctions_list()` |
| Brent, WTI, USD/INR | Yahoo Finance via `yfinance` | `fetch_commodity_prices()` |
| SPR & refinery stocks | PIB press releases (manual, cited) | `buffer_config.json` |
| Import mix / transit | PPAC Monthly Import Data (template) | `import_mix.json` (fill manually) |

---

## 📦 Dependencies

### Python (`requirements.txt`)
```
feedparser>=6.0.0          # RSS parsing
requests>=2.31.0           # HTTP
beautifulsoup4>=4.12.0     # HTML scraping
lxml>=4.9.0                # HTML parser
pandas>=2.0.0              # Data manipulation
psycopg2-binary>=2.9.0     # Postgres (optional — skip with --no-db)
fastapi>=0.111.0           # REST API
uvicorn[standard]>=0.29.0  # ASGI server
python-multipart>=0.0.9    # FastAPI form support
newspaper3k>=0.2.8         # Article full-text extraction
yfinance>=0.2.40           # Yahoo Finance market data
schedule>=1.2.0            # Optional scheduler
python-dateutil>=2.8.0     # Date parsing
```

### Node.js (`frontend/`)
```
react, react-dom            # UI framework
vite, @vitejs/plugin-react  # Build tool
tailwindcss, @tailwindcss/vite  # Styling
leaflet, react-leaflet      # Interactive map
recharts                    # Commodity price charts
dayjs                       # Relative timestamps in news feed
react-is                    # Recharts peer dependency
```

---

## 🗺️ API Reference (Quick)

### `GET /api/risk-corridors`
```json
{
  "corridors": [
    {
      "corridor": "hormuz",
      "score": 74.2,
      "level": "red",
      "event_count": 12,
      "top_headlines": [{"title": "...", "date": "..."}]
    }
  ],
  "scored_at": "2026-07-17T00:00:00Z"
}
```

### `GET /api/news-feed?limit=40&days=7&corridor=hormuz&category=Shipping_Chokepoints`
```json
{
  "items": [
    {
      "title": "...", "source": "...", "link": "...",
      "date": "2026-07-16", "category": "Shipping_Chokepoints",
      "corridor": "hormuz", "severity": 4,
      "buffer_layer": "on_water", "key_takeaway": "..."
    }
  ],
  "count": 14
}
```

### `GET /api/buffer-stack`
```json
{
  "layers": [
    {"layer": "on_water",       "days_cover": null, "methodology": "estimated", "display_badge": "Estimated"},
    {"layer": "refinery_stock", "days_cover": 64.5, "methodology": "official_published", "display_badge": "PIB Verified"},
    {"layer": "spr",            "days_cover": 6.1,  "methodology": "official_published", "display_badge": "PIB + Rajya Sabha RTI Verified"}
  ],
  "total_days_cover": 70.6
}
```

### `GET /api/commodity-prices?days=30`
```json
{
  "series": [
    {"ticker": "BZ=F", "points": [{"date": "2026-07-16", "close": 85.4}]},
    {"ticker": "CL=F", "points": [...]},
    {"ticker": "INR=X","points": [...]}
  ],
  "as_of": "2026-07-17T00:00:00Z"
}
```

### `GET /api/sanctions/recent?days=30`
```json
{
  "new_designations": [
    {"ent_num": "12345", "name": "...", "type": "Individual", "fetched_at": "..."}
  ],
  "count": 3
}
```

---

## 📋 Your Remaining Action Items

| Priority | Task | Where |
|---|---|---|
| 🔴 Before demo | Fill `import_share_pct` per country | `backend/config/import_mix.json` |
| 🔴 Before demo | Set `daily_consumption_bbl` | `backend/config/import_mix.json` |
| 🔴 Before demo | Re-verify SPR fill % against ISPRL/PPAC | `backend/config/buffer_config.json` → `current_fill_pct` |
| 🟡 Optional | Set `VITE_API_URL` for deployed backend | `frontend/.env` |
| 🟡 Optional | Add DB migration for 3 new columns | `macro_events` table: add `buffer_layer VARCHAR`, `corridor VARCHAR`, `severity INT` |
| 🟢 Future | Build Scenario Simulator panel | Replace `PlaceholderCard` in `App.jsx` |
| 🟢 Future | Build Procurement Recommendation Engine | Replace `PlaceholderCard` in `App.jsx` |
| 🟢 Future | Build Decision Meter | Replace `PlaceholderCard` in `App.jsx` |

---

## 🔄 How to Run the Pipeline on a Schedule (Optional)

The pipeline is stateless — call it on any cron schedule:

**Windows Task Scheduler (PowerShell):**
```powershell
$action = New-ScheduledTaskAction -Execute "python" `
  -Argument '"C:\...\backend\live_macro_pipeline.py" --from-date (Get-Date).AddDays(-7).ToString("yyyy-MM-dd") --to-date (Get-Date).ToString("yyyy-MM-dd") --no-db' `
  -WorkingDirectory "C:\...\backend"
$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 30) -Once -At (Get-Date)
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "EnergyPipeline"
```

**Or use the `schedule` library:**
```python
import schedule, time, subprocess

def run_pipeline():
    subprocess.run(["python", "live_macro_pipeline.py",
                    "--from-date", "...", "--to-date", "...", "--no-db"])

schedule.every(30).minutes.do(run_pipeline)
while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## ⚠️ Important Data Integrity Notes

1. **SPR fill % is dynamic** — the 64% figure in `buffer_config.json` is from March 2026. Re-verify against ISPRL press releases before your final presentation.

2. **On-water days are estimated** — `calculate_on_water_days()` derives this mathematically from import mix data. It is **never** "live" or "real-time". Always displayed with an "Estimated" badge.

3. **News scores decay** — corridor risk scores use a 36-hour exponential half-life. Scores drop automatically as events age, even without a new pipeline run.

4. **No mock data anywhere** — every number in the system traces to either a live scrape, a Yahoo Finance fetch, or an explicitly cited government publication.

---

*Built for PS2: AI-Driven Energy Supply Chain Resilience for Import-Dependent Economies*
