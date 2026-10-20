"""Functions that read and write the tracker's data."""
from tracker.db import get_db

TOTAL_STATES = 50


def get_states():
    """Return all states sorted A to Z, each with a `visited` flag (1 or 0).

    EXISTS (...) is a yes/no check: is there at least one visit for this state?
    """
    return get_db().execute(
        """
        SELECT id, code, name,
               EXISTS (SELECT 1 FROM visits WHERE visits.state_id = states.id) AS visited
        FROM states
        ORDER BY name
        """
    ).fetchall()


def get_state(code):
    """Return one state by its code (any upper/lower case), or None if there's no such state."""
    return get_db().execute(
        "SELECT id, code, name FROM states WHERE code = ?", (code.upper(),)
    ).fetchone()


def get_visits_for_state(state_id):
    """Return one state's visits, newest first.

    If two visits share a date, the one added later comes first (higher id).
    """
    return get_db().execute(
        """
        SELECT visit_date, note FROM visits
        WHERE state_id = ?
        ORDER BY visit_date DESC, id DESC
        """,
        (state_id,),
    ).fetchall()


def add_visit(state_code, visit_date, note):
    """Save one visit. Expects input that already passed validate_visit().

    The ? marks are placeholders: SQLite fills in the values safely, so text
    typed into the form can never be run as SQL.
    """
    db = get_db()
    db.execute(
        """
        INSERT INTO visits (state_id, visit_date, note)
        VALUES ((SELECT id FROM states WHERE code = ?), ?, ?)
        """,
        (state_code, visit_date, note),
    )
    db.commit()


def count_visited_states():
    """Return how many different states have at least one visit.

    COUNT(DISTINCT ...) counts each state once, even with several visits.
    """
    return get_db().execute("SELECT COUNT(DISTINCT state_id) FROM visits").fetchone()[0]


def save_trip_states(db, trip_id, state_codes):
    """Link a trip to each of its states. Used when adding and when editing a trip.

    INSERT OR IGNORE skips a state that's already on the trip, so ticking the
    same state twice saves it once.
    """
    for code in state_codes:
        db.execute(
            """
            INSERT OR IGNORE INTO trip_states (trip_id, state_id)
            VALUES (?, (SELECT id FROM states WHERE code = ?))
            """,
            (trip_id, code),
        )


def add_trip(name, start_date, end_date, state_codes):
    """Save a planned trip and its states, and return the new trip's id.

    Expects input that passed validate_trip().
    """
    db = get_db()
    # cursor.lastrowid is the id SQLite gave the row we just inserted.
    cursor = db.execute(
        "INSERT INTO trips (name, start_date, end_date) VALUES (?, ?, ?)",
        (name, start_date, end_date),
    )
    trip_id = cursor.lastrowid
    save_trip_states(db, trip_id, state_codes)
    db.commit()
    return trip_id


def get_trip(trip_id):
    """Return one trip as a dictionary with a list of its state codes, or None if it doesn't exist."""
    row = get_db().execute(
        "SELECT id, name, start_date, end_date FROM trips WHERE id = ?", (trip_id,)
    ).fetchone()
    if row is None:
        return None
    trip = dict(row)
    trip["states"] = [state["code"] for state in get_trip_states(trip_id)]
    return trip


def update_trip(trip_id, name, start_date, end_date, state_codes):
    """Change a trip's name, dates and states. Expects input that passed validate_trip().

    The simplest way to change the states is to remove them all and add the
    new list back.
    """
    db = get_db()
    db.execute(
        "UPDATE trips SET name = ?, start_date = ?, end_date = ? WHERE id = ?",
        (name, start_date, end_date, trip_id),
    )
    db.execute("DELETE FROM trip_states WHERE trip_id = ?", (trip_id,))
    save_trip_states(db, trip_id, state_codes)
    db.commit()


def delete_trip(trip_id):
    """Delete a trip. Its trip_states rows go too, thanks to ON DELETE CASCADE in schema.sql.

    Visits live in their own table, so they're never touched.
    """
    db = get_db()
    db.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
    db.commit()


def get_trip_states(trip_id):
    """Return the states on one trip, A to Z."""
    return get_db().execute(
        """
        SELECT states.code, states.name FROM trip_states
        JOIN states ON states.id = trip_states.state_id
        WHERE trip_states.trip_id = ?
        ORDER BY states.name
        """,
        (trip_id,),
    ).fetchall()


def get_upcoming_trips(today, state_id=None):
    """Return trips that haven't ended yet, soonest first, each with its states.

    A trip that's happening right now (end date today or later) still counts.
    Pass `state_id` to get only the trips that include that state.

    The result is a list of dictionaries, e.g.
    {"name": "Weekend", "start_date": ..., "end_date": ..., "states": [...]}.
    """
    query = "SELECT id, name, start_date, end_date FROM trips WHERE end_date >= ?"
    params = [today.isoformat()]
    if state_id is not None:
        query += " AND id IN (SELECT trip_id FROM trip_states WHERE state_id = ?)"
        params.append(state_id)
    query += " ORDER BY start_date, id"

    trips = []
    for row in get_db().execute(query, params).fetchall():
        # dict(row) copies the row into a normal dictionary we can add to.
        trip = dict(row)
        trip["states"] = get_trip_states(row["id"])
        trips.append(trip)
    return trips


def get_state_statuses(today, year=None):
    """Return each state's map color as {code: "visited" | "planned" | "unvisited"}.

    "visited" means at least one visit. Otherwise "planned" means the state is
    in a trip that hasn't ended. Visited wins when both are true. With `year`,
    only trips that start in that year count as planned.
    """
    db = get_db()
    visited = {row[0] for row in db.execute(
        "SELECT DISTINCT states.code FROM visits JOIN states ON states.id = visits.state_id"
    )}

    query = """
        SELECT DISTINCT states.code FROM trip_states
        JOIN trips ON trips.id = trip_states.trip_id
        JOIN states ON states.id = trip_states.state_id
        WHERE trips.end_date >= ?
    """
    params = [today.isoformat()]
    if year is not None:
        # substr(text, 1, 4) takes the first 4 characters: the year of "2027-03-01".
        query += " AND substr(trips.start_date, 1, 4) = ?"
        params.append(str(year))
    planned = {row[0] for row in db.execute(query, params)}

    statuses = {}
    for state in get_states():
        if state["code"] in visited:
            statuses[state["code"]] = "visited"
        elif state["code"] in planned:
            statuses[state["code"]] = "planned"
        else:
            statuses[state["code"]] = "unvisited"
    return statuses


def get_trip_years(today):
    """Return the years that upcoming trips start in, e.g. [2026, 2027], earliest first."""
    rows = get_db().execute(
        "SELECT DISTINCT substr(start_date, 1, 4) FROM trips WHERE end_date >= ? ORDER BY 1",
        (today.isoformat(),),
    )
    return [int(row[0]) for row in rows]
