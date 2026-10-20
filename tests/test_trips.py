"""Slice 4: planned trips, and the rules a trip must follow."""
import re
from datetime import date, timedelta
from html import unescape

from tracker.db import get_db
from tracker.models import add_trip
from tracker.validation import validate_trip

# A fixed "today" for the validation tests, so they give the same result
# no matter what day you run them.
TODAY = date(2026, 10, 20)


def days_from_now(days):
    """Helper: a real date relative to today, as "YYYY-MM-DD", for the page tests."""
    return (date.today() + timedelta(days=days)).isoformat()


def post_trip(client, name="Four Corners weekend", start=None, end=None, states=("AZ", "UT")):
    """Helper: submit the new-trip form. By default, a valid trip next week."""
    return client.post(
        "/trips/new",
        data={
            "name": name,
            "start_date": start if start is not None else days_from_now(7),
            "end_date": end if end is not None else days_from_now(9),
            # A list value sends the field several times, like ticking several checkboxes.
            "states": list(states),
        },
    )


def count_trips(app):
    """Helper: how many trips are in the test database."""
    with app.app_context():
        return get_db().execute("SELECT COUNT(*) FROM trips").fetchone()[0]


def page_text(client, url):
    """Helper: fetch a page and return its text as the browser would show it."""
    return unescape(client.get(url).get_data(as_text=True))


# --- The rules, checked directly (no web page involved) ---------------------

def test_valid_trip_has_no_errors():
    assert validate_trip("Weekend", "2026-11-06", "2026-11-08", ["AZ", "UT"], TODAY) == []


def test_trip_starting_tomorrow_is_allowed():
    assert validate_trip("Weekend", "2026-10-21", "2026-10-22", ["AZ"], TODAY) == []


def test_trip_starting_today_is_rejected():
    """Hard rule: a trip must start in the future, and today isn't the future."""
    errors = validate_trip("Weekend", "2026-10-20", "2026-10-22", ["AZ"], TODAY)
    assert "A planned trip must start in the future." in errors


def test_trip_starting_in_the_past_is_rejected():
    errors = validate_trip("Weekend", "2026-01-01", "2026-01-03", ["AZ"], TODAY)
    assert "A planned trip must start in the future." in errors


def test_end_before_start_is_rejected():
    """Hard rule: the end date can't be before the start date."""
    errors = validate_trip("Weekend", "2026-11-08", "2026-11-06", ["AZ"], TODAY)
    assert "The end date can't be before the start date." in errors


def test_one_day_trip_is_allowed():
    """End on the same day as the start is fine."""
    assert validate_trip("Day trip", "2026-11-06", "2026-11-06", ["AZ"], TODAY) == []


def test_trip_needs_a_name():
    errors = validate_trip("   ", "2026-11-06", "2026-11-08", ["AZ"], TODAY)
    assert "Please enter a trip name." in errors


def test_trip_needs_both_dates():
    errors = validate_trip("Weekend", "", "", ["AZ"], TODAY)
    assert "Please enter a start date." in errors
    assert "Please enter an end date." in errors


def test_trip_with_impossible_dates_is_rejected():
    errors = validate_trip("Weekend", "2027-02-30", "2027-02-31", ["AZ"], TODAY)
    assert "Please enter a real start date." in errors
    assert "Please enter a real end date." in errors


def test_trip_needs_at_least_one_state():
    errors = validate_trip("Weekend", "2026-11-06", "2026-11-08", [], TODAY)
    assert "Please choose at least one state." in errors


def test_trip_to_an_unknown_state_is_rejected():
    """Exactly 50 states, so D.C. can't be part of a trip."""
    errors = validate_trip("Weekend", "2026-11-06", "2026-11-08", ["VA", "DC"], TODAY)
    assert "Please choose only from the 50 states." in errors


# --- The new-trip page -------------------------------------------------------

def test_new_trip_form_has_a_checkbox_for_each_state(client):
    page = client.get("/trips/new").get_data(as_text=True)
    assert len(re.findall(r'type="checkbox" name="states" value="[A-Z]{2}"', page)) == 50


def test_adding_a_trip_with_two_states_saves_it(app, client):
    response = post_trip(client)
    # After saving, you're sent to the trips list.
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/trips")

    with app.app_context():
        db = get_db()
        trip = db.execute("SELECT name, start_date, end_date FROM trips").fetchone()
        codes = [row[0] for row in db.execute(
            "SELECT states.code FROM trip_states"
            " JOIN states ON states.id = trip_states.state_id ORDER BY states.code"
        )]
    assert tuple(trip) == ("Four Corners weekend", days_from_now(7), days_from_now(9))
    assert codes == ["AZ", "UT"]


def test_same_state_ticked_twice_is_saved_once(app, client):
    post_trip(client, states=("AZ", "AZ"))
    with app.app_context():
        count = get_db().execute("SELECT COUNT(*) FROM trip_states").fetchone()[0]
    assert count == 1


def test_trip_to_an_already_visited_state_is_allowed(app, client):
    """Rule: I can plan a trip to a state I've already visited."""
    client.post("/visits/new", data={"state": "AZ", "visit_date": "2024-07-04", "note": ""})
    response = post_trip(client, states=("AZ",))
    assert response.status_code == 302
    assert count_trips(app) == 1


def test_trip_starting_today_is_not_saved_and_shows_an_error(app, client):
    response = post_trip(client, start=days_from_now(0), end=days_from_now(1))
    # 400 means "Bad Request": the form is shown again with the error.
    assert response.status_code == 400
    assert "A planned trip must start in the future." in unescape(response.get_data(as_text=True))
    assert count_trips(app) == 0


def test_trip_without_states_is_not_saved(app, client):
    response = post_trip(client, states=())
    assert response.status_code == 400
    assert count_trips(app) == 0


def test_form_keeps_what_you_typed_after_an_error(client):
    response = post_trip(client, name="Four Corners weekend", start=days_from_now(0), states=("AZ", "UT"))
    page = response.get_data(as_text=True)
    assert 'value="Four Corners weekend"' in page
    assert 'value="AZ" checked' in page
    assert 'value="UT" checked' in page
    assert 'value="CA" checked' not in page


def test_planned_trip_does_not_count_as_visited(client):
    """Progress counts visits only. Planning a trip isn't visiting."""
    post_trip(client, states=("AZ", "UT"))
    assert "0 of 50" in page_text(client, "/trips")


# --- The trips list ----------------------------------------------------------

def test_trips_page_lists_a_trip_with_its_dates_and_states(client):
    post_trip(client, name="Four Corners weekend", states=("AZ", "UT"))
    page = page_text(client, "/trips")
    assert "Four Corners weekend" in page
    assert days_from_now(7) in page
    assert days_from_now(9) in page
    assert "Arizona" in page
    assert "Utah" in page


def test_trips_are_listed_soonest_first(client):
    post_trip(client, name="Later trip", start=days_from_now(30), end=days_from_now(31))
    post_trip(client, name="Sooner trip", start=days_from_now(5), end=days_from_now(6))
    page = page_text(client, "/trips")
    assert page.index("Sooner trip") < page.index("Later trip")


def test_trips_that_already_ended_are_not_listed(app, client):
    """A trip planned long ago is over now. It was saved directly, skipping
    the form, because the form (rightly) won't accept past dates."""
    with app.app_context():
        add_trip("Last summer", "2025-06-01", "2025-06-03", ["OR"])
    assert "Last summer" not in page_text(client, "/trips")


def test_trip_in_progress_is_still_listed(app, client):
    """Started yesterday, ends tomorrow: still worth seeing."""
    with app.app_context():
        add_trip("This weekend", days_from_now(-1), days_from_now(1), ["OR"])
    assert "This weekend" in page_text(client, "/trips")


def test_no_trips_says_so(client):
    assert "No trips planned yet." in page_text(client, "/trips")


def test_nav_links_to_trips(client):
    page = client.get("/states").get_data(as_text=True)
    assert 'href="/trips"' in page
    assert 'href="/trips/new"' in client.get("/trips").get_data(as_text=True)


# --- Trips on the state page -------------------------------------------------

def test_state_page_shows_planned_trips_including_it(client):
    post_trip(client, name="Four Corners weekend", states=("AZ", "UT"))
    assert "Four Corners weekend" in page_text(client, "/states/AZ")
    assert "Four Corners weekend" in page_text(client, "/states/UT")
    assert "Four Corners weekend" not in page_text(client, "/states/CA")
