# TIER 1 & 2 Task List

> **Handoff note (2026-07-18, audited by Antigravity session 2):**  
> Items marked [x] below were **personally verified** by live endpoint testing this session, not just claimed complete.  
> Items marked [!] are **newly discovered issues** found during reconciliation.  
> Items marked [ ] are genuinely not started.

---

## Infrastructure Fix (discovered during reconciliation)
- [x] Fix `venv/pyvenv.cfg` — was pointing to `C:\Users\DELL\...` (different machine). Patched to `C:\Users\ASUS\...`. **Verified working.**

## Pre-flight
- [x] Fix Nigeria `transit_days_typica` typo in import_mix.json

## Component 1 — Response Agent
- [x] Create `backend/agent/__init__.py`
- [x] Create `backend/agent/response_agent.py`
- [x] Create `backend/api/routers/auto_alerts.py`
- [x] Update `backend/api/main.py` (register router + background thread lifespan)
- [x] Update `backend/.env.example` (GEMINI_API_KEY — was ANTHROPIC, now correctly Gemini)

## Component 2 — LLM Signal Validation
- [x] Add `classify_with_llm()` to `live_macro_pipeline.py` (opt-in `--llm-classify`) — **uses Google Gemini 2.0 Flash, rate-limit safe, capped at 40**
- [x] Update `backend/api/routers/news_feed.py` (expose llm columns + `llm_stats`) — **verified: llm_stats present in response**

## Component 3 — LLM Procurement Justifications
- [ ] **INCOMPLETE** — `generate_justification()` in `scenario_analysis.py` still calls `anthropic.Anthropic(api_key=...)` with `claude-haiku-4-5`. Needs migration to Gemini.

## Component 4 — RAG Corridor Brief (Tier 2, but router exists)
- [x] Create `backend/api/routers/corridor_brief.py` and register in main.py — **file exists, endpoint returns 200**
- [ ] **INCOMPLETE** — `synthesize_brief()` in `corridor_brief.py` still calls `anthropic.Anthropic(api_key=...)` with `claude-haiku-4-5`. Needs migration to Gemini.
- [x] Create `frontend/src/components/CorridorBrief.jsx`
- [x] Wire `<CorridorBrief />` into `App.jsx` (Risk Agent tab, line 291)

## Frontend
- [x] Update `frontend/src/config.js` (autoAlerts + corridorBrief endpoints) — **verified present**
- [x] Create `frontend/src/components/AutoAlerts.jsx` — **file exists (11KB)**
- [x] Update `frontend/src/App.jsx` (add AutoAlerts + CorridorBrief + signal validation stats row) — **verified wired in**

## Verification
- [x] `/api/risk-corridors` — **personally tested, 200 OK, real data (hormuz=100, 7 corridors)**
- [x] `/api/news-feed` — **personally tested, 200 OK, real articles**
- [x] `/api/auto-alerts` — **personally tested, 200 OK, 3 real hormuz alerts**
- [x] `/api/corridor-brief` — **personally tested, 200 OK, fallback brief (expected — no Gemini key set)**
- [x] Backend starts without crash — **confirmed, agent thread fires correctly**
- [ ] `/api/auto-alerts` — frontend "Feed Error" was caused by broken venv, not code. **Now resolved.** Frontend should work once backend is running via `.\venv\Scripts\python.exe -m uvicorn api.main:app --port 8000 --app-dir backend`

---

## Remaining Work — Gemini Migration (INCOMPLETE)

### Migrate `corridor_brief.py` to Gemini
- [ ] Replace `import anthropic` / `anthropic.Anthropic(...)` / `claude-haiku-4-5` with `google.genai` + `gemini-2.0-flash`
- [ ] Read key from `os.environ.get("GEMINI_API_KEY", "")`

### Migrate `scenario_analysis.py` to Gemini
- [ ] Replace `import anthropic` / `anthropic.Anthropic(...)` / `claude-haiku-4-5` with `google.genai` + `gemini-2.0-flash`
- [ ] Read key from `os.environ.get("GEMINI_API_KEY", "")`

### Minor cleanup
- [ ] `api/main.py` docstring line 21: change `ANTHROPIC_API_KEY` reference to `GEMINI_API_KEY`
- [ ] `App.jsx` line 314: `"Anthropic Claude · last 7 days"` → `"Google Gemini · last 7 days"`

### Install google-genai in venv
- [ ] `.\venv\Scripts\python.exe -m pip install google-genai` — package is missing from venv; `--llm-classify` flag will fail with ImportError without it

---

## TIER 2 — Additional Resiliency Features

### 5. Real Geospatial Depth
- [ ] Add static coordinates for refineries, ports, and SPR sites to `WorldMap.jsx`
- [ ] Add "estimated vessels in transit" calculation & configuration to `scenario_assumptions.json`
- [ ] Display vessel estimation clearly in the UI

### 6. Lightweight Knowledge Graph
- [x] `backend/agent/knowledge_graph.py` exists and is imported by `response_agent.py`
- [ ] Use graph programmatically in the Disruption Response Agent for exposed exposure checks

### 7. Historical Score Tracking + Trend
- [x] `corridor_score_history.csv` is being written (51KB, confirmed exists)
- [x] Trend calculation in `risk_corridors.py` (`_trend_from_history()`)
- [x] `trend` field returned in `/api/risk-corridors` response
- [ ] Trend indicators (rising/falling arrows) exposed in frontend corridor risk panel
