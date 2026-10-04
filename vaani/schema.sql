PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS sessions (
 id TEXT PRIMARY KEY,
 created_at TEXT NOT NULL,
 language TEXT NOT NULL,
 source TEXT NOT NULL,
 planner TEXT NOT NULL,
 prompt_version TEXT NOT NULL,
 state_json TEXT NOT NULL,
 outcome TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS turns (
 id INTEGER PRIMARY KEY,
 session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
 request_id TEXT NOT NULL,
 request_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,
 user_text TEXT NOT NULL,
 agent_text TEXT NOT NULL,
 intent TEXT NOT NULL,
 state_before TEXT NOT NULL,
 state_after TEXT NOT NULL,
 latency_ms REAL NOT NULL,
 planner_status TEXT NOT NULL,
 response_json TEXT NOT NULL,
 UNIQUE(session_id, request_id)
);
CREATE TABLE IF NOT EXISTS bookings (
 id TEXT PRIMARY KEY,
 session_id TEXT UNIQUE NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
 city TEXT NOT NULL,
 slot TEXT NOT NULL,
 created_at TEXT NOT NULL,
 UNIQUE(city, slot)
);
CREATE TABLE IF NOT EXISTS eval_runs (
 id TEXT PRIMARY KEY,
 created_at TEXT NOT NULL,
 planner TEXT NOT NULL,
 prompt_version TEXT NOT NULL,
 total INTEGER NOT NULL,
 passed INTEGER NOT NULL,
 result_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS turns_session ON turns(session_id, id);
CREATE INDEX IF NOT EXISTS sessions_outcome ON sessions(outcome);
CREATE TABLE IF NOT EXISTS voice_events (
 id INTEGER PRIMARY KEY,
 session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL,
 kind TEXT NOT NULL,
 value REAL,
 detail TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS voice_events_session ON voice_events(session_id,id);
