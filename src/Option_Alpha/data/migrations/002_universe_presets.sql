-- Migration 002: Universe filter presets.
-- Stores saved filter configurations for the universe browser.

CREATE TABLE IF NOT EXISTS universe_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    filters TEXT NOT NULL,         -- JSON: {"sectors": [...], "tiers": [...], "sources": [...], "active_only": true}
    created_at TEXT NOT NULL
);
