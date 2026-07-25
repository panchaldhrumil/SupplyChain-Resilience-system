import hashlib
import json
from datetime import datetime, timezone

import psycopg2

from pipeline.settings import DATABASE_URL, DATABASE_URL_UNPOOLED


def get_connection():
    # Prefer unpooled direct connection (avoids Neon pooler data-transfer quota)
    url = DATABASE_URL_UNPOOLED or DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    return conn


def init_schema(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS macro_events (
                id SERIAL PRIMARY KEY,
                date DATE,
                title TEXT,
                source TEXT,
                link TEXT,
                category TEXT,
                affected_sectors TEXT,
                affected_companies TEXT,
                buffer_layer TEXT DEFAULT 'none',
                corridor TEXT DEFAULT 'none',
                severity INTEGER DEFAULT 0,
                extracted_numbers TEXT,
                key_takeaway TEXT,
                article_text_snippet TEXT,
                fetch_status TEXT,
                llm_severity INTEGER,
                llm_confidence FLOAT,
                is_genuine_disruption TEXT,
                llm_corridor TEXT,
                llm_justification TEXT,
                review_flagged BOOLEAN,
                llm_status TEXT,
                content_hash TEXT UNIQUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_me_date ON macro_events (date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_me_corridor ON macro_events (corridor)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_me_category ON macro_events (category)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS commodity_prices (
                id SERIAL PRIMARY KEY,
                date DATE,
                ticker TEXT,
                label TEXT,
                open FLOAT,
                high FLOAT,
                low FLOAT,
                close FLOAT,
                volume BIGINT,
                fetched_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(date, ticker)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sanctions (
                id SERIAL PRIMARY KEY,
                ent_num TEXT UNIQUE,
                sdn_name TEXT,
                sdn_type TEXT,
                program TEXT,
                title TEXT,
                call_sign TEXT,
                vess_type TEXT,
                tonnage TEXT,
                grt TEXT,
                vess_flag TEXT,
                vess_owner TEXT,
                remarks TEXT,
                fetched_at TIMESTAMPTZ DEFAULT NOW(),
                new_since_last_run BOOLEAN DEFAULT FALSE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id SERIAL PRIMARY KEY,
                cycle_id TEXT,
                triggered_at TIMESTAMPTZ,
                corridor TEXT,
                score_prev FLOAT,
                score_now FLOAT,
                threshold FLOAT,
                signal_detected_at TIMESTAMPTZ,
                scenario_computed_at TIMESTAMPTZ,
                recommendation_generated_at TIMESTAMPTZ,
                latency_ms INTEGER,
                supply_gap_pct FLOAT,
                coverage_days FLOAT,
                buffer_status TEXT,
                top_recommendation TEXT,
                top_score FLOAT,
                all_affected_suppliers TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS corridor_score_history (
                id SERIAL PRIMARY KEY,
                ts TIMESTAMPTZ DEFAULT NOW(),
                cycle_id TEXT,
                corridor TEXT,
                score FLOAT,
                level TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_csh_corridor ON corridor_score_history (corridor)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_state (
                id INTEGER PRIMARY KEY DEFAULT 1,
                scores JSONB,
                saved_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)


def compute_content_hash(title):
    return hashlib.sha256(str(title).encode()).hexdigest()


def fetch_existing_hashes(conn):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT content_hash FROM macro_events WHERE content_hash IS NOT NULL")
            return {row[0] for row in cur.fetchall()}
    except Exception as e:
        print(f"[DB] fetch_existing_hashes: {e}")
        return set()


def _safe_int(v, default=0):
    try:
        if v is None or v == "":
            return default
        return int(float(v))
    except Exception:
        return default


def _safe_float(v, default=None):
    try:
        if v is None or v == "":
            return default
        f = float(v)
        return None if (f != f) else f
    except Exception:
        return default


def upsert_macro_events(conn, rows):
    if not rows:
        return 0, 0
    from psycopg2.extras import execute_values
    tuples = []
    for row in rows:
        h = compute_content_hash(row.get("title", ""))
        tuples.append((
            str(row.get("event_date", ""))[:10] or None,
            str(row.get("title", "")),
            str(row.get("source", "")),
            str(row.get("link", "")),
            str(row.get("category", "")),
            str(row.get("affected_sectors", "")),
            str(row.get("affected_companies", "")),
            str(row.get("buffer_layer", "none") or "none"),
            str(row.get("corridor", "none") or "none"),
            _safe_int(row.get("severity"), 0),
            str(row.get("extracted_numbers", "")),
            str(row.get("key_takeaway", "")),
            str(row.get("article_text_snippet", "")),
            str(row.get("fetch_status", "")),
            h,
        ))

    query = """
        INSERT INTO macro_events (
            date, title, source, link, category,
            affected_sectors, affected_companies,
            buffer_layer, corridor, severity,
            extracted_numbers, key_takeaway,
            article_text_snippet, fetch_status, content_hash
        ) VALUES %s
        ON CONFLICT (content_hash) DO NOTHING
    """
    try:
        with conn.cursor() as cur:
            execute_values(cur, query, tuples, page_size=500)
        return len(tuples), 0
    except Exception as e:
        print(f"[DB] upsert_macro_events batch failed: {e}")
        return 0, len(tuples)


def upsert_commodity_prices(conn, rows):
    if not rows:
        return 0
    from psycopg2.extras import execute_values
    tuples = []
    for row in rows:
        tuples.append((
            str(row.get("date", ""))[:10] or None,
            str(row.get("ticker", "")),
            str(row.get("label", "")),
            _safe_float(row.get("open")),
            _safe_float(row.get("high")),
            _safe_float(row.get("low")),
            _safe_float(row.get("close")),
            _safe_int(row.get("volume"), 0),
        ))

    query = """
        INSERT INTO commodity_prices (date, ticker, label, open, high, low, close, volume)
        VALUES %s
        ON CONFLICT (date, ticker) DO NOTHING
    """
    try:
        with conn.cursor() as cur:
            execute_values(cur, query, tuples, page_size=500)
        return len(tuples)
    except Exception as e:
        print(f"[DB] upsert_commodity_prices batch failed: {e}")
        return 0


def upsert_sanctions(conn, rows):
    if not rows:
        return 0
    from psycopg2.extras import execute_values
    tuples = []
    for row in rows:
        ent = str(row.get("ent_num", "")).strip()
        if not ent:
            continue
        is_new = str(row.get("new_since_last_run", "False")).strip().lower() in ("true", "1", "yes")
        tuples.append((
            ent,
            str(row.get("sdn_name", "")),
            str(row.get("sdn_type", "")),
            str(row.get("program", "")),
            str(row.get("title", "")),
            str(row.get("call_sign", "")),
            str(row.get("vess_type", "")),
            str(row.get("tonnage", "")),
            str(row.get("grt", "")),
            str(row.get("vess_flag", "")),
            str(row.get("vess_owner", "")),
            str(row.get("remarks", "")),
            is_new,
        ))

    if not tuples:
        return 0

    query = """
        INSERT INTO sanctions (
            ent_num, sdn_name, sdn_type, program, title,
            call_sign, vess_type, tonnage, grt, vess_flag,
            vess_owner, remarks, new_since_last_run
        ) VALUES %s
        ON CONFLICT (ent_num) DO UPDATE SET
            new_since_last_run = EXCLUDED.new_since_last_run,
            fetched_at = NOW()
    """
    chunk_size = 1000
    total = 0
    try:
        with conn.cursor() as cur:
            for i in range(0, len(tuples), chunk_size):
                chunk = tuples[i:i + chunk_size]
                execute_values(cur, query, chunk, page_size=chunk_size)
                total += len(chunk)
        return total
    except Exception as e:
        print(f"[DB] upsert_sanctions batch failed: {e}")
        return 0


def get_existing_sanction_ids(conn):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT ent_num FROM sanctions")
            return {str(r[0]).strip() for r in cur.fetchall()}
    except Exception:
        return set()


def _migrate_alerts_columns(conn):
    """One-time migration: add new sub-step latency and coverage_note columns if missing."""
    new_cols = {
        "signal_to_scenario_ms":      "INTEGER",
        "scenario_to_procurement_ms": "INTEGER",
        "procurement_to_llm_ms":      "INTEGER",
        "coverage_note":              "TEXT",
    }
    try:
        with conn.cursor() as cur:
            for col, col_type in new_cols.items():
                cur.execute("""
                    DO $$ BEGIN
                        ALTER TABLE alerts ADD COLUMN IF NOT EXISTS {col} {col_type};
                    EXCEPTION WHEN others THEN NULL;
                    END $$;
                """.replace("{col}", col).replace("{col_type}", col_type))
    except Exception as e:
        print(f"[DB] migrate_alerts_columns: {e}")


def append_alert(conn, row):
    _migrate_alerts_columns(conn)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO alerts (
                    cycle_id, triggered_at, corridor,
                    score_prev, score_now, threshold,
                    signal_detected_at, scenario_computed_at,
                    recommendation_generated_at, latency_ms,
                    signal_to_scenario_ms, scenario_to_procurement_ms, procurement_to_llm_ms,
                    supply_gap_pct, coverage_days, coverage_note, buffer_status,
                    top_recommendation, top_score, all_affected_suppliers
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                str(row.get("cycle_id", "")),
                row.get("triggered_at"),
                str(row.get("corridor", "")),
                _safe_float(row.get("score_prev")),
                _safe_float(row.get("score_now")),
                _safe_float(row.get("threshold")),
                row.get("signal_detected_at"),
                row.get("scenario_computed_at"),
                row.get("recommendation_generated_at"),
                _safe_int(row.get("latency_ms")),
                _safe_int(row.get("signal_to_scenario_ms")),
                _safe_int(row.get("scenario_to_procurement_ms")),
                _safe_int(row.get("procurement_to_llm_ms")),
                _safe_float(row.get("supply_gap_pct")),
                _safe_float(row.get("coverage_days")),
                str(row.get("coverage_note") or ""),
                str(row.get("buffer_status", "")),
                str(row.get("top_recommendation", "")),
                _safe_float(row.get("top_score")),
                str(row.get("all_affected_suppliers", "")),
            ))
    except Exception as e:
        print(f"[DB] append_alert failed: {e}")


def append_score_history(conn, scores, cycle_id):
    try:
        now_ts = datetime.now(timezone.utc)
        with conn.cursor() as cur:
            for corridor, score in scores.items():
                score_val = round(float(score), 1)
                level = "red" if score_val >= 66 else "amber" if score_val >= 33 else "green"
                cur.execute("""
                    INSERT INTO corridor_score_history (ts, cycle_id, corridor, score, level)
                    VALUES (%s,%s,%s,%s,%s)
                """, (now_ts, cycle_id, corridor, score_val, level))
    except Exception as e:
        print(f"[DB] append_score_history failed: {e}")


def save_agent_state(conn, scores):
    try:
        now_ts = datetime.now(timezone.utc)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO agent_state (id, scores, saved_at)
                VALUES (1, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    scores = EXCLUDED.scores,
                    saved_at = EXCLUDED.saved_at
            """, (json.dumps(scores), now_ts))
    except Exception as e:
        print(f"[DB] save_agent_state failed: {e}")


def load_agent_state(conn):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT scores FROM agent_state WHERE id = 1")
            row = cur.fetchone()
            if row and row[0]:
                return {"scores": row[0]}
    except Exception:
        pass
    return None


def cleanup_db_logs(conn, keep_days=3):
    """
    Automated 4-hour cleanup job:
    Deletes macro_events older than keep_days (default 3 days) to keep
    Neon DB size minimal and stay well within free tier limits.
    """
    if conn is None:
        return 0
    try:
        with conn.cursor() as cur:
            cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
            cur.execute("DELETE FROM macro_events WHERE date < %s", (cutoff.date(),))
            deleted_events = cur.rowcount
            cur.execute("DELETE FROM corridor_score_history WHERE ts < %s", (cutoff,))
            deleted_history = cur.rowcount
            print(f"[DB Cleanup] Deleted {deleted_events} old news items and {deleted_history} old score history records (older than {keep_days} days).")
            return deleted_events
    except Exception as e:
        print(f"[DB Cleanup] Failed: {e}")
        return 0

    return {}
