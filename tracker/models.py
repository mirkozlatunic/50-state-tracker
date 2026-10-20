"""Functions that read and write the tracker's data."""
from collections import Counter
from datetime import date

from tracker.cities import find_city
from tracker.db import get_db
from tracker.regions_data import REGIONS

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
    """Return one state's visits (date, note and city), newest first.

    If two visits share a date, the one added later comes first (higher id).
    """
    return get_db().execute(
        """
        SELECT visit_date, note, city FROM visits
        WHERE state_id = ?
        ORDER BY visit_date DESC, id DESC
        """,
        (state_id,),
    ).fetchall()


def add_visit(state_code, visit_date, note, city=None):
    """Save one visit. Expects input that already passed validate_visit().

    `city` is the official city name, or None for a visit without a city.
    The ? marks are placeholders: SQLite fills in the values safely, so text
    typed into the form can never be run as SQL.
    """
    db = get_db()
    db.execute(
        """
        INSERT INTO visits (state_id, visit_date, note, city)
        VALUES ((SELECT id FROM states WHERE code = ?), ?, ?, ?)
        """,
        (state_code, visit_date, note, city),
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


def save_trip_cities(db, trip_id, cities):
    """Link a trip to its cities, given as (official name, state code) pairs."""
    for name, code in cities:
        db.execute(
            """
            INSERT OR IGNORE INTO trip_cities (trip_id, state_id, city)
            VALUES (?, (SELECT id FROM states WHERE code = ?), ?)
            """,
            (trip_id, code, name),
        )


def get_trip_cities(trip_id):
    """Return a trip's cities as rows with `city` and `code`, A to Z."""
    return get_db().execute(
        """
        SELECT trip_cities.city, states.code FROM trip_cities
        JOIN states ON states.id = trip_cities.state_id
        WHERE trip_cities.trip_id = ?
        ORDER BY trip_cities.city
        """,
        (trip_id,),
    ).fetchall()


def add_trip(name, start_date, end_date, state_codes, cities=()):
    """Save a planned trip, its states and its cities, and return the new trip's id.

    Expects input that passed validate_trip() and validate_trip_cities().
    `cities` is a list of (official name, state code) pairs; it's optional.
    """
    db = get_db()
    # cursor.lastrowid is the id SQLite gave the row we just inserted.
    cursor = db.execute(
        "INSERT INTO trips (name, start_date, end_date) VALUES (?, ?, ?)",
        (name, start_date, end_date),
    )
    trip_id = cursor.lastrowid
    save_trip_states(db, trip_id, state_codes)
    save_trip_cities(db, trip_id, cities)
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
    # As the form shows them: "Denver, CO".
    trip["cities"] = [f"{row['city']}, {row['code']}" for row in get_trip_cities(trip_id)]
    return trip


def update_trip(trip_id, name, start_date, end_date, state_codes, cities=()):
    """Change a trip's name, dates, states and cities. Expects input that passed validation.

    The simplest way to change the states and cities is to remove them all and
    add the new lists back.
    """
    db = get_db()
    db.execute(
        "UPDATE trips SET name = ?, start_date = ?, end_date = ? WHERE id = ?",
        (name, start_date, end_date, trip_id),
    )
    db.execute("DELETE FROM trip_states WHERE trip_id = ?", (trip_id,))
    save_trip_states(db, trip_id, state_codes)
    db.execute("DELETE FROM trip_cities WHERE trip_id = ?", (trip_id,))
    save_trip_cities(db, trip_id, cities)
    db.commit()


def delete_trip(trip_id):
    """Delete a trip. Its trip_states and trip_cities rows go too (ON DELETE CASCADE in schema.sql).

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
        trip["cities"] = get_trip_cities(row["id"])
        trips.append(trip)
    return trips


def get_visited_codes():
    """Return the codes of every state with at least one visit, as a set like {"CA", "NV"}."""
    return {row[0] for row in get_db().execute(
        "SELECT DISTINCT states.code FROM visits JOIN states ON states.id = visits.state_id"
    )}


def get_state_statuses(today, year=None):
    """Return each state's map color as {code: "visited" | "planned" | "unvisited"}.

    "visited" means at least one visit. Otherwise "planned" means the state is
    in a trip that hasn't ended. Visited wins when both are true. With `year`,
    only trips that start in that year count as planned.
    """
    db = get_db()
    visited = get_visited_codes()

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


def get_year_plan(today):
    """Return one dictionary per year, for the year page, earliest year first.

    Each one looks like:
    {"year": 2027, "trips": [...], "new_states": ["Colorado", ...], "total_by_end": 15}

    - Years run from this year to the year of the last planned trip, and
      always include at least this year and the next two.
    - A trip belongs to the year it starts in. A trip that's still going but
      started last year (say Dec 30 to Jan 2) shows in this year.
    - "new_states" are states in that year's trips that you haven't visited
      and didn't already plan in an earlier year.
    - "total_by_end" is how many states you'll have by the end of that year:
      the visited ones plus every planned one so far, each counted once.
    """
    trips = get_upcoming_trips(today)
    for trip in trips:
        trip["year"] = max(int(trip["start_date"][:4]), today.year)

    # default= is what max() gives back when the list is empty (no trips).
    last_year = max([trip["year"] for trip in trips], default=today.year)
    last_year = max(last_year, today.year + 2)

    counted = get_visited_codes()
    plan = []
    for year in range(today.year, last_year + 1):
        year_trips = [trip for trip in trips if trip["year"] == year]
        new_states = {}
        for trip in year_trips:
            for state in trip["states"]:
                if state["code"] not in counted:
                    new_states[state["code"]] = state["name"]
        # "|=" adds everything from the right-hand side into the set.
        counted |= set(new_states)
        plan.append({
            "year": year,
            "trips": year_trips,
            "new_states": sorted(new_states.values()),
            "total_by_end": len(counted),
        })
    return plan


def shift_to_year(start_date, end_date, year):
    """Work out a trip's dates in another year. Returns (new_start, new_end) as dates.

    The start keeps its month and day, and the trip keeps its length, so a
    Dec 30 to Jan 2 trip still ends in the following year. Feb 29 becomes
    Feb 28 in a year without a leap day.
    """
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    # Subtracting two dates gives a "timedelta": a length of time, here in days.
    length = end - start
    try:
        new_start = start.replace(year=year)
    except ValueError:
        # replace() fails only for Feb 29 in a year that doesn't have one.
        new_start = date(year, 2, 28)
    return new_start, new_start + length


def set_trip_dates(trip_id, start_date, end_date):
    """Change only a trip's dates (used when moving it to another year)."""
    db = get_db()
    db.execute(
        "UPDATE trips SET start_date = ?, end_date = ? WHERE id = ?",
        (start_date, end_date, trip_id),
    )
    db.commit()


def get_city_dots(today, year=None):
    """Return the cities to draw as dots on the map, one dictionary per city.

    Each one looks like:
    {"name": "Denver", "state": "CO", "x": 331.6, "y": 257.9, "kind": "upcoming",
     "visit_dates": ["2024-07-04"], "trips": [("Four Corners weekend", "2026-10-30")]}

    - Every city with a visit gets a dot (visit dates oldest first).
    - Every city in a trip that hasn't ended gets one too. With `year`, only
      trips that start in that year count.
    - "kind" is "upcoming" if the city is in an upcoming trip (even if you've
      been there before), otherwise "visited".
    """
    db = get_db()
    found = {}

    def info_for(code, name):
        """The dictionary for one city, made the first time we see it."""
        return found.setdefault((code, name), {"visit_dates": [], "trips": []})

    for row in db.execute(
        """
        SELECT states.code, visits.city, visits.visit_date FROM visits
        JOIN states ON states.id = visits.state_id
        WHERE visits.city IS NOT NULL
        ORDER BY visits.visit_date
        """
    ):
        info_for(row["code"], row["city"])["visit_dates"].append(row["visit_date"])

    query = """
        SELECT states.code, trip_cities.city, trips.name, trips.start_date FROM trip_cities
        JOIN trips ON trips.id = trip_cities.trip_id
        JOIN states ON states.id = trip_cities.state_id
        WHERE trips.end_date >= ?
    """
    params = [today.isoformat()]
    if year is not None:
        query += " AND substr(trips.start_date, 1, 4) = ?"
        params.append(str(year))
    query += " ORDER BY trips.start_date, trips.id"
    for row in db.execute(query, params):
        info_for(row["code"], row["city"])["trips"].append((row["name"], row["start_date"]))

    dots = []
    for (code, name), info in sorted(found.items()):
        city = find_city(name, code)
        if city is None:
            continue  # not in the city list (e.g. the list was rebuilt without it)
        dots.append({
            "name": city.name,
            "state": code,
            "x": city.x,
            "y": city.y,
            "kind": "upcoming" if info["trips"] else "visited",
            "visit_dates": info["visit_dates"],
            "trips": info["trips"],
        })
    return dots


def get_regions(today, year=None):
    """Return the four Census regions for the region cards, each as a dictionary:

    {"name": "West", "total": 13, "visited": 6, "planned": 2,
     "visited_percent": 46.2, "planned_percent": 15.4,
     "states": [{"code": "AK", "name": "Alaska", "status": "planned", "city_count": 0}, ...]}

    A state's status follows the same rules as the map (get_state_statuses),
    including the `year` filter. city_count is how many different cities
    you've visited there.
    """
    statuses = get_state_statuses(today, year=year)
    names = {state["code"]: state["name"] for state in get_states()}
    # Counter counts things: here, visited cities per state.
    city_counts = Counter(dot["state"] for dot in get_city_dots(today) if dot["visit_dates"])

    regions = []
    for region_name, codes in REGIONS:
        states = sorted(
            ({"code": code, "name": names[code], "status": statuses[code],
              "city_count": city_counts[code]} for code in codes),
            key=lambda state: state["name"],
        )
        visited = sum(1 for state in states if state["status"] == "visited")
        planned = sum(1 for state in states if state["status"] == "planned")
        regions.append({
            "name": region_name,
            "total": len(codes),
            "visited": visited,
            "planned": planned,
            "visited_percent": round(100 * visited / len(codes), 1),
            "planned_percent": round(100 * planned / len(codes), 1),
            "states": states,
        })
    return regions


def get_next_trip(today):
    """Return the soonest trip that hasn't ended, with a "when" text, or None.

    "when" is "happening now" (already started), "tomorrow", or "in 10 days".
    """
    trips = get_upcoming_trips(today)
    if not trips:
        return None
    trip = trips[0]
    days = (date.fromisoformat(trip["start_date"]) - today).days
    if days <= 0:
        trip["when"] = "happening now"
    elif days == 1:
        trip["when"] = "tomorrow"
    else:
        trip["when"] = f"in {days} days"
    return trip
