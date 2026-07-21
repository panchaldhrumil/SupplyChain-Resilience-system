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
);

CREATE INDEX IF NOT EXISTS idx_me_date ON macro_events (date);
CREATE INDEX IF NOT EXISTS idx_me_corridor ON macro_events (corridor);
CREATE INDEX IF NOT EXISTS idx_me_category ON macro_events (category);
CREATE INDEX IF NOT EXISTS idx_me_date_corridor ON macro_events (date, corridor);

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
);

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
);

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
);

CREATE TABLE IF NOT EXISTS corridor_score_history (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMPTZ DEFAULT NOW(),
    cycle_id TEXT,
    corridor TEXT,
    score FLOAT,
    level TEXT
);

CREATE INDEX IF NOT EXISTS idx_csh_corridor ON corridor_score_history (corridor);
CREATE INDEX IF NOT EXISTS idx_csh_ts ON corridor_score_history (ts);

CREATE TABLE IF NOT EXISTS agent_state (
    id INTEGER PRIMARY KEY DEFAULT 1,
    scores JSONB,
    saved_at TIMESTAMPTZ DEFAULT NOW()
);
