-- backend/migrations/001_add_corridor_columns.sql
-- Run this ONCE when enabling Postgres mode (removing --no-db flag).
-- Adds the three corridor-impact columns produced by Phase 1 pipeline work.
-- Safe to run multiple times — uses ADD COLUMN IF NOT EXISTS.

ALTER TABLE macro_events
  ADD COLUMN IF NOT EXISTS buffer_layer VARCHAR(32) DEFAULT 'none',
  ADD COLUMN IF NOT EXISTS corridor     VARCHAR(64) DEFAULT 'none',
  ADD COLUMN IF NOT EXISTS severity     INT         DEFAULT 0;

-- Optionally index corridor for faster risk-corridor API queries:
-- CREATE INDEX IF NOT EXISTS idx_macro_events_corridor ON macro_events (corridor);
-- CREATE INDEX IF NOT EXISTS idx_macro_events_date_corridor ON macro_events (date, corridor);
