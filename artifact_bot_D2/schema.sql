-- Schema for Telegram Lead Alert Bot
-- SQLite WAL mode and indices for deduplication

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS seen_leads (
    lead_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    budget TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_seen_leads_url ON seen_leads(url);
