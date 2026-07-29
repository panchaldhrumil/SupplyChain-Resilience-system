import os
import threading
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
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

_BACKEND_DIR = Path(__file__).parent.parent
CSV_OUTPUT_DIR = Path(os.environ.get("CSV_OUTPUT_DIR") or str(_BACKEND_DIR / "data" / "macro_events"))
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR") or str(_BACKEND_DIR / "config"))


def _init_db():
    try:
        from pipeline.db import get_connection, init_schema
        conn = get_connection()
        init_schema(conn)
        conn.close()
        log.info("Neon DB schema initialised.")
    except Exception as e:
        log.warning("DB schema init failed (non-fatal): %s", e)


def _init_qdrant():
    try:
        from pipeline.qdrant_store import get_client, ensure_collection
        client = get_client()
        if client:
            ensure_collection(client)
            log.info("Qdrant collection ready.")
    except Exception as e:
        log.warning("Qdrant init failed (non-fatal): %s", e)


def _start_agent_loop():
    try:
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


def _start_pipeline_scheduler():
    try:
        from scheduler import start_scheduler_thread
        interval_hours = int(os.environ.get("PIPELINE_INTERVAL_HOURS", 1))
        run_on_startup = os.environ.get("PIPELINE_RUN_ON_STARTUP", "true").lower() in ("true", "1", "t")
        start_scheduler_thread(interval_hours=interval_hours, run_now=run_on_startup)
        log.info("Integrated News Pipeline Scheduler started (interval=%dh, run_now=%s).", interval_hours, run_on_startup)
    except Exception as e:
        log.warning("Could not start background pipeline scheduler: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_db()
    _init_qdrant()
    # Daemon threads removed — agent loop and scheduler do not work on Vercel Serverless
    yield


app = FastAPI(
    title="India Energy Supply Chain Resilience API",
    description=(
        "Real-data API for the PS2 hackathon dashboard. "
        "All endpoints read from Neon Postgres (with CSV fallback). "
        "Semantic search via Qdrant. "
        "Autonomous agent loop (response_agent.py) fires auto-alerts when "
        "corridor risk scores cross the configurable threshold."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.csv_dir    = CSV_OUTPUT_DIR
app.state.config_dir = CONFIG_DIR

app.include_router(risk_corridors.router,    prefix="/api")
app.include_router(news_feed.router,         prefix="/api")
app.include_router(commodity_prices.router,  prefix="/api")
app.include_router(sanctions.router,         prefix="/api")
app.include_router(buffer_stack.router,      prefix="/api")
app.include_router(scenario_analysis.router, prefix="/api")
app.include_router(auto_alerts.router,       prefix="/api")
app.include_router(corridor_brief.router,    prefix="/api")


@app.post("/api/trigger-pipeline")
def trigger_pipeline():
    try:
        from scheduler import is_pipeline_running, trigger_manual_run
        if is_pipeline_running():
            return {"status": "busy", "message": "Pipeline run is already in progress."}
        trigger_manual_run()
        return {"status": "triggered", "message": "Pipeline run launched in background."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/health")
def health():
    import os as _os
    from datetime import datetime as _dt, timezone as _tz

    db_ok = False
    db_error = None
    try:
        from pipeline.db import get_connection
        _conn = get_connection()
        _conn.close()
        db_ok = True
    except Exception as e:
        db_error = str(e)

    pipeline_running = False
    try:
        from scheduler import is_pipeline_running
        pipeline_running = is_pipeline_running()
    except Exception:
        pass

    return {
        "status":           "ok",
        "db_connected":     db_ok,
        "db_error":         db_error,
        "pipeline_running": pipeline_running,
        "csv_output_dir":   str(CSV_OUTPUT_DIR),
        "config_dir":       str(CONFIG_DIR),
        "agent_threshold":  float(_os.environ.get("AGENT_THRESHOLD", 66.0)),
        "agent_interval_s": int(_os.environ.get("AGENT_INTERVAL_SECONDS", 300)),
    }
