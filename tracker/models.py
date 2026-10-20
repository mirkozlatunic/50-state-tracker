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
