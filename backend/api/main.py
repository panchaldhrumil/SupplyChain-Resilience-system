"""
backend/api/main.py
====================
FastAPI application for the India Energy Supply Chain Resilience dashboard.

Reads directly from CSVs written by live_macro_pipeline.py — no Postgres
dependency required for the API layer to function. Every data point served
traces back to a real scraped or fetched source.

Run locally:
    cd backend
    uvicorn api.main:app --reload --port 8000

Environment variables (override defaults):
    CSV_OUTPUT_DIR   — path to the directory where live_macro_pipeline.py
                       writes its CSVs (default: backend/data/macro_events/)
    CONFIG_DIR       — path to backend/config/ (default: auto-detected
                       relative to this file's location)
    AGENT_THRESHOLD          — corridor score that triggers auto-alert (default: 66)
    AGENT_INTERVAL_SECONDS   — how often the agent loop runs (default: 300)
    ANTHROPIC_API_KEY        — required for --llm-classify pipeline flag and
                               ?llm_justify=true procurement endpoint
"""

import os
import threading
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import (
    risk_corridors,
    news_feed,
    commodity_prices,
    sanctions,
    buffer_stack,
    scenario_analysis,
    auto_alerts,
    corridor_brief,
)

log = logging.getLogger("api.main")

# --------------------------------------------------------------------------
# Settings  (env-var overrideable, sensible defaults)
# --------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).parent.parent   # backend/
CSV_OUTPUT_DIR = Path(os.environ.get(
    "CSV_OUTPUT_DIR",
    str(_BACKEND_DIR / "data" / "macro_events"),
))

_THIS_DIR = Path(__file__).parent          # backend/api/
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", str(_THIS_DIR.parent / "config")))


# --------------------------------------------------------------------------
# Agent background thread
# --------------------------------------------------------------------------

def _start_agent_loop():
    """Start response_agent's run_loop() as a daemon thread."""
    try:
        # Import lazily so a broken agent module doesn't crash the whole API.
        from agent.response_agent import run_loop
        t = threading.Thread(target=run_loop, daemon=True, name="response-agent")
        t.start()
        log.info("Disruption Response Agent started (daemon thread).")
    except Exception as e:
        log.warning(
            "Could not start response agent thread: %s. "
            "API will still serve all endpoints; agent must be run manually via "
            "`python -m agent.response_agent`.",
            e,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: start agent on startup, clean up on shutdown."""
    _start_agent_loop()
    yield
    # Daemon thread dies automatically with the process.


# --------------------------------------------------------------------------
# FastAPI app
# --------------------------------------------------------------------------
app = FastAPI(
    title="India Energy Supply Chain Resilience API",
    description=(
        "Real-data API for the PS2 hackathon dashboard. "
        "All endpoints read from CSVs produced by live_macro_pipeline.py "
        "or from cited config files (buffer_config.json). "
        "No mock data anywhere. "
        "Autonomous agent loop (response_agent.py) fires auto-alerts when "
        "corridor risk scores cross the configurable threshold."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow Vite dev server (localhost:5173) and production origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------
# Share settings with routers via app.state
# --------------------------------------------------------------------------
app.state.csv_dir    = CSV_OUTPUT_DIR
app.state.config_dir = CONFIG_DIR

# --------------------------------------------------------------------------
# Routers
# --------------------------------------------------------------------------
app.include_router(risk_corridors.router,   prefix="/api")
app.include_router(news_feed.router,        prefix="/api")
app.include_router(commodity_prices.router, prefix="/api")
app.include_router(sanctions.router,        prefix="/api")
app.include_router(buffer_stack.router,     prefix="/api")
app.include_router(scenario_analysis.router, prefix="/api")
app.include_router(auto_alerts.router,      prefix="/api")
app.include_router(corridor_brief.router,   prefix="/api")


@app.get("/api/health")
def health():
    """Quick liveness check — also shows CSV dir config and last pipeline run time."""
    import os as _os
    from datetime import datetime as _dt, timezone as _tz

    master_csv = CSV_OUTPUT_DIR / "macro_events_filtered.csv"
    last_csv_mtime = None
    if master_csv.exists():
        mtime_ts = _os.path.getmtime(master_csv)
        last_csv_mtime = _dt.fromtimestamp(mtime_ts, tz=_tz.utc).isoformat()

    alerts_csv = CSV_OUTPUT_DIR / "auto_triggered_alerts.csv"
    alerts_exist = alerts_csv.exists()

    state_file = CSV_OUTPUT_DIR / "agent_state.json"
    agent_last_run = None
    if state_file.exists():
        try:
            import json
            with open(state_file) as f:
                st = json.load(f)
            agent_last_run = st.get("saved_at")
        except Exception:
            pass

    return {
        "status":            "ok",
        "csv_output_dir":    str(CSV_OUTPUT_DIR),
        "csv_dir_exists":    CSV_OUTPUT_DIR.exists(),
        "config_dir":        str(CONFIG_DIR),
        "last_csv_mtime":    last_csv_mtime,
        "agent_last_run":    agent_last_run,
        "alerts_csv_exists": alerts_exist,
        "agent_threshold":   float(_os.environ.get("AGENT_THRESHOLD", 66.0)),
        "agent_interval_s":  int(_os.environ.get("AGENT_INTERVAL_SECONDS", 300)),
    }
