"""Slice 6: the clickable US map. Green = visited, orange = in an upcoming trip."""
import re
from datetime import date, timedelta

from tracker.map_data import STATE_PATHS
from tracker.models import add_trip, get_state_statuses
from tests.test_states import EXPECTED_STATES


def days_from_now(days):
    """Helper: a real date relative to today, as "YYYY-MM-DD"."""
    return (date.today() + timedelta(days=days)).isoformat()


def add_visit(client, state, visit_date="2024-07-04"):
    """Helper: add one visit through the form, like you would in the browser."""
    client.post("/visits/new", data={"state": state, "visit_date": visit_date, "note": ""})


def make_trip(app, start, end, states):
    """Helper: save a trip directly (skipping the form), so tests can also make past trips."""
    with app.app_context():
        add_trip("Test trip", start, end, list(states))


def map_page(client, url="/map"):
    """Helper: the map page as HTML text."""
    return client.get(url).get_data(as_text=True)


def state_class(page, code):
    """Helper: the color class the map gives one state: visited, planned or unvisited."""
    match = re.search(rf'id="state-{code}" class="state (\w+)"', page)
    return match.group(1) if match else None


# --- The map data --------------------------------------------------------------

def test_map_data_has_exactly_the_50_states():
    """Same 50 codes as the states list. D.C. is left out."""
    assert set(STATE_PATHS) == set(EXPECTED_STATES)
    assert "DC" not in STATE_PATHS


# --- Working out each state's color --------------------------------------------

def test_states_start_unvisited(app):
    with app.app_context():
        statuses = get_state_statuses(date.today())
    assert len(statuses) == 50
    assert set(statuses.values()) == {"unvisited"}


def test_visited_state_is_visited(app, client):
    add_visit(client, "CA")
    with app.app_context():
        assert get_state_statuses(date.today())["CA"] == "visited"


def test_state_in_an_upcoming_trip_is_planned(app):
    make_trip(app, days_from_now(7), days_from_now(9), ["AZ", "UT"])
    with app.app_context():
        statuses = get_state_statuses(date.today())
    assert statuses["AZ"] == "planned"
    assert statuses["UT"] == "planned"
    assert statuses["CA"] == "unvisited"


def test_visited_beats_planned(app, client):
    """A state that's visited AND in an upcoming trip shows as visited (green)."""
    add_visit(client, "AZ")
    make_trip(app, days_from_now(7), days_from_now(9), ["AZ"])
    with app.app_context():
        assert get_state_statuses(date.today())["AZ"] == "visited"


def test_trip_that_has_ended_is_not_planned(app):
    make_trip(app, "2025-06-01", "2025-06-03", ["OR"])
    with app.app_context():
        assert get_state_statuses(date.today())["OR"] == "unvisited"


def test_trip_in_progress_still_counts_as_planned(app):
    make_trip(app, days_from_now(-1), days_from_now(1), ["OR"])
    with app.app_context():
        assert get_state_statuses(date.today())["OR"] == "planned"


def test_year_filter_only_counts_trips_starting_that_year(app):
    """A trip belongs to the year it starts in."""
    this_year = date.today().year
    # Starts today, so it's this year's trip (and hasn't ended).
    make_trip(app, days_from_now(0), days_from_now(0), ["AZ"])
    make_trip(app, f"{this_year + 1}-03-01", f"{this_year + 1}-03-03", ["UT"])
    with app.app_context():
        this = get_state_statuses(date.today(), year=this_year)
        nxt = get_state_statuses(date.today(), year=this_year + 1)
    assert (this["AZ"], this["UT"]) == ("planned", "unvisited")
    assert (nxt["AZ"], nxt["UT"]) == ("unvisited", "planned")


# --- The map page ----------------------------------------------------------------

def test_map_page_draws_50_states(client):
    page = map_page(client)
    assert page.count('class="state ') == 50
    for code in EXPECTED_STATES:
        assert f'id="state-{code}"' in page
    assert 'id="state-DC"' not in page


def test_every_state_links_to_its_page(client):
    page = map_page(client)
    for code in EXPECTED_STATES:
        assert f'href="/states/{code}"' in page


def test_hovering_a_state_shows_its_name(client):
    """An SVG <title> inside a shape is shown as a tooltip by the browser."""
    page = map_page(client)
    assert "<title>California</title>" in page
    assert "<title>Rhode Island</title>" in page


def test_map_colors_follow_visits_and_trips(app, client):
    add_visit(client, "CA")
    make_trip(app, days_from_now(7), days_from_now(9), ["AZ"])
    page = map_page(client)
    assert state_class(page, "CA") == "visited"
    assert state_class(page, "AZ") == "planned"
    assert state_class(page, "TX") == "unvisited"


def test_map_page_year_filter(app, client):
    this_year = date.today().year
    make_trip(app, f"{this_year + 1}-03-01", f"{this_year + 1}-03-03", ["UT"])
    assert state_class(map_page(client), "UT") == "planned"
    assert state_class(map_page(client, f"/map?year={this_year}"), "UT") == "unvisited"
    assert state_class(map_page(client, f"/map?year={this_year + 1}"), "UT") == "planned"


def test_year_filter_offers_the_years_with_trips(app, client):
    this_year = date.today().year
    make_trip(app, f"{this_year + 1}-03-01", f"{this_year + 1}-03-03", ["UT"])
    page = map_page(client)
    assert f'href="/map?year={this_year + 1}"' in page
    assert 'href="/map"' in page  # "All upcoming trips"


def test_bad_year_in_the_address_is_ignored(app, client):
    """/map?year=banana shows the normal map instead of crashing."""
    make_trip(app, days_from_now(7), days_from_now(9), ["AZ"])
    response = client.get("/map?year=banana")
    assert response.status_code == 200
    assert state_class(response.get_data(as_text=True), "AZ") == "planned"


def test_map_has_a_legend(client):
    page = map_page(client)
    for label in ("Visited", "Planned", "Not visited yet"):
        assert label in page


def test_map_page_shows_the_counter_and_nav_has_a_map_link(client):
    add_visit(client, "CA")
    assert "1 of 50" in map_page(client)
    assert 'href="/map"' in client.get("/states").get_data(as_text=True)
