-- Tables for the tracker.
-- "IF NOT EXISTS" means running this file again keeps your existing data.

CREATE TABLE IF NOT EXISTS states (
    id   INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,  -- e.g. "CA"
    name TEXT UNIQUE NOT NULL   -- e.g. "California"
);

-- Visits are added in slice 2. The table exists now so the progress
-- counter can already count visited states (0 to start with).
CREATE TABLE IF NOT EXISTS visits (
    id         INTEGER PRIMARY KEY,
    state_id   INTEGER NOT NULL REFERENCES states(id),
    visit_date TEXT NOT NULL,   -- "YYYY-MM-DD"
    note       TEXT NOT NULL DEFAULT ''
);
