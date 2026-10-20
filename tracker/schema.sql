-- Tables for the tracker.
-- "IF NOT EXISTS" means running this file again keeps your existing data.

CREATE TABLE IF NOT EXISTS states (
    id   INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,  -- e.g. "CA"
    name TEXT UNIQUE NOT NULL   -- e.g. "California"
);

-- One row per visit. A state can have several; progress counts each state once.
CREATE TABLE IF NOT EXISTS visits (
    id         INTEGER PRIMARY KEY,
    state_id   INTEGER NOT NULL REFERENCES states(id),
    visit_date TEXT NOT NULL,   -- "YYYY-MM-DD"
    note       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS trips (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    start_date TEXT NOT NULL,   -- "YYYY-MM-DD"
    end_date   TEXT NOT NULL,   -- "YYYY-MM-DD"
    -- A backstop for the rule; the app checks it first with a friendly message.
    CHECK (end_date >= start_date)
);

-- A "join table": one row per (trip, state) pair, so one trip can have many
-- states. The PRIMARY KEY on both columns stops the same state being added twice.
CREATE TABLE IF NOT EXISTS trip_states (
    trip_id  INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    state_id INTEGER NOT NULL REFERENCES states(id),
    PRIMARY KEY (trip_id, state_id)
);
