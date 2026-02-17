-- Migration 001: Initial schema for Option Alpha persistence layer.
-- Creates tables for scan runs, ticker scores, AI theses, and watchlists.

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scan_runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    preset TEXT NOT NULL,
    sectors TEXT NOT NULL,        -- JSON array of sector strings
    ticker_count INTEGER NOT NULL,
    top_n INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ticker_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_run_id TEXT NOT NULL REFERENCES scan_runs(id),
    ticker TEXT NOT NULL,
    composite_score REAL NOT NULL,
    direction TEXT NOT NULL,
    score_breakdown TEXT NOT NULL, -- JSON dict of signal -> score
    rank INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_theses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    direction TEXT NOT NULL,
    conviction REAL NOT NULL,
    model_used TEXT NOT NULL,
    total_tokens INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    entry_rationale TEXT NOT NULL,
    risk_factors TEXT NOT NULL,          -- JSON array of risk factor strings
    recommended_action TEXT NOT NULL,
    bull_summary TEXT NOT NULL,
    bear_summary TEXT NOT NULL,
    disclaimer TEXT NOT NULL,
    full_thesis TEXT NOT NULL            -- JSON of entire TradeThesis for future-proofing
);

CREATE TABLE IF NOT EXISTS watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist_tickers (
    watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (watchlist_id, ticker)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_ticker_scores_scan_run ON ticker_scores(scan_run_id);
CREATE INDEX IF NOT EXISTS idx_ticker_scores_ticker ON ticker_scores(ticker);
CREATE INDEX IF NOT EXISTS idx_ai_theses_ticker ON ai_theses(ticker);
CREATE INDEX IF NOT EXISTS idx_ai_theses_direction ON ai_theses(direction);
