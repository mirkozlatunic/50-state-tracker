"""Slice 2: adding visits, and the rules a visit must follow."""
from datetime import date, timedelta
from html import unescape

from tracker.db import get_db
from tracker.validation import validate_visit

# A fixed "today" for the validation tests, so they give the same result
# no matter what day you run them.
TODAY = date(2026, 10, 20)


def count_visits(app):
    """Helper: how many visit rows are in the test database."""
    with app.app_context():
        return get_db().execute("SELECT COUNT(*) FROM visits").fetchone()[0]


# --- The rules, checked directly (no web page involved) ---------------------

def test_valid_visit_has_no_errors():
    assert validate_visit("CA", "2024-07-04", TODAY) == []


def test_visit_today_is_allowed():
    """Today is not in the future, so it is fine."""
    assert validate_visit("CA", "2026-10-20", TODAY) == []


def test_visit_in_the_future_is_rejected():
    """Hard rule: a visit date can't be in the future."""
    errors = validate_visit("CA", "2026-10-21", TODAY)
    assert "The visit date can't be in the future." in errors


def test_visit_without_a_date_is_rejected():
    errors = validate_visit("CA", "", TODAY)
    assert "Please enter a visit date." in errors


def test_visit_with_an_impossible_date_is_rejected():
    """February 30th doesn't exist."""
    errors = validate_visit("CA", "2024-02-30", TODAY)
    assert "Please enter a real date." in errors


def test_visit_to_an_unknown_state_is_rejected(app):
    """Hard rule: exactly 50 states, so D.C. or a typo can't be visited.

    This check needs the database (to look up the state), so it uses `app`.
    """
    with app.app_context():
        errors = validate_visit("DC", "2024-07-04", TODAY)
    assert "Please choose one of the 50 states." in errors


# --- The add-visit page ------------------------------------------------------

def test_add_visit_form_lists_all_50_states(client):
    page = client.get("/visits/new").get_data(as_text=True)
    assert page.count("<option value=") == 50


def test_add_visit_form_explains_layovers_dont_count(client):
    """Rule: only time outside the airport counts. The app can't check this,
    so the form reminds you."""
    page = client.get("/visits/new").get_data(as_text=True)
    assert "outside the airport" in page


def test_adding_a_visit_saves_it(app, client):
    response = client.post(
        "/visits/new",
        data={"state": "CA", "visit_date": "2024-07-04", "note": "Big Sur road trip"},
    )
    # After saving, you're sent back to the states list.
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/states")

    with app.app_context():
        visit = get_db().execute(
            "SELECT states.code, visit_date, note FROM visits"
            " JOIN states ON states.id = visits.state_id"
        ).fetchone()
    assert tuple(visit) == ("CA", "2024-07-04", "Big Sur road trip")


def test_note_is_optional(app, client):
    client.post("/visits/new", data={"state": "NV", "visit_date": "2024-07-05", "note": ""})
    assert count_visits(app) == 1


def test_future_visit_is_not_saved_and_shows_an_error(app, client):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    response = client.post(
        "/visits/new", data={"state": "CA", "visit_date": tomorrow, "note": ""}
    )
    # 400 means "Bad Request": the form is shown again with the error.
    assert response.status_code == 400
    # unescape() turns HTML codes like &#39; back into characters like ' so we
    # check the text as the browser would show it.
    page = unescape(response.get_data(as_text=True))
    assert "The visit date can't be in the future." in page
    assert count_visits(app) == 0


def test_unknown_state_is_not_saved(app, client):
    response = client.post(
        "/visits/new", data={"state": "DC", "visit_date": "2024-07-04", "note": ""}
    )
    assert response.status_code == 400
    assert count_visits(app) == 0


def test_form_keeps_what_you_typed_after_an_error(client):
    """So you don't have to type the note again."""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    response = client.post(
        "/visits/new", data={"state": "CA", "visit_date": tomorrow, "note": "Big Sur"}
    )
    assert "Big Sur" in response.get_data(as_text=True)


def test_states_page_has_a_link_to_add_a_visit(client):
    page = client.get("/states").get_data(as_text=True)
    assert 'href="/visits/new"' in page
