"""Slice 7: the year page. One column per year with its trips and states."""
import re
from datetime import date, timedelta
from html import unescape

from tracker.models import add_trip, add_visit, get_year_plan

# A fixed "today" for the get_year_plan() tests, so they give the same result
# no matter what day you run them.
TODAY = date(2026, 10, 20)


def days_from_now(days):
    """Helper: a real date relative to today, as "YYYY-MM-DD", for the page tests."""
    return (date.today() + timedelta(days=days)).isoformat()


def make_trip(app, name, start, end, states):
    """Helper: save a trip directly (skipping the form) and return its id."""
    with app.app_context():
        return add_trip(name, start, end, list(states))


def plan(app, today=TODAY):
    """Helper: get_year_plan() as {year: that year's plan}."""
    with app.app_context():
        return {year_plan["year"]: year_plan for year_plan in get_year_plan(today)}


def page_text(client, url):
    """Helper: fetch a page and return its text as the browser would show it."""
    return unescape(client.get(url).get_data(as_text=True))


# --- Working out the plan (fixed "today": 2026-10-20) --------------------------

def test_shows_this_year_and_the_next_two_when_there_are_no_trips(app):
    assert list(plan(app)) == [2026, 2027, 2028]


def test_shows_more_years_when_trips_are_planned_further_ahead(app):
    make_trip(app, "Far away", "2030-06-01", "2030-06-03", ["HI"])
    assert list(plan(app)) == [2026, 2027, 2028, 2029, 2030]


def test_trip_belongs_to_the_year_it_starts_in(app):
    """A trip from Dec 30 to Jan 2 is in the year it starts."""
    make_trip(app, "New Year's", "2026-12-30", "2027-01-02", ["NY"])
    years = plan(app)
    assert [t["name"] for t in years[2026]["trips"]] == ["New Year's"]
    assert years[2027]["trips"] == []


def test_trips_in_a_year_are_soonest_first(app):
    make_trip(app, "Later", "2027-09-01", "2027-09-02", ["ME"])
    make_trip(app, "Sooner", "2027-03-01", "2027-03-02", ["VT"])
    assert [t["name"] for t in plan(app)[2027]["trips"]] == ["Sooner", "Later"]


def test_trips_that_have_ended_are_left_out(app):
    make_trip(app, "Last summer", "2026-06-01", "2026-06-03", ["OR"])
    assert plan(app)[2026]["trips"] == []


def test_new_states_leave_out_visited_ones(app):
    with app.app_context():
        add_visit("AZ", "2024-07-04", "")
    make_trip(app, "Four Corners", "2027-03-01", "2027-03-03", ["AZ", "UT", "CO", "NM"])
    assert plan(app)[2027]["new_states"] == ["Colorado", "New Mexico", "Utah"]


def test_state_planned_twice_is_new_only_in_the_first_year(app):
    """By the time of the second trip you'll already have been there."""
    make_trip(app, "First", "2027-03-01", "2027-03-02", ["VT"])
    make_trip(app, "Again", "2028-03-01", "2028-03-02", ["VT", "NH"])
    years = plan(app)
    assert years[2027]["new_states"] == ["Vermont"]
    assert years[2028]["new_states"] == ["New Hampshire"]


def test_total_by_end_of_year_adds_up_and_counts_each_state_once(app):
    """Visited states + every planned state up to that year, each counted once."""
    with app.app_context():
        add_visit("CA", "2024-07-04", "")
        add_visit("AZ", "2024-07-05", "")
    make_trip(app, "Four Corners", "2027-03-01", "2027-03-03", ["AZ", "UT"])
    make_trip(app, "New England", "2028-09-01", "2028-09-04", ["VT", "UT"])
    years = plan(app)
    assert years[2026]["total_by_end"] == 2  # CA, AZ
    assert years[2027]["total_by_end"] == 3  # + UT (AZ already visited)
    assert years[2028]["total_by_end"] == 4  # + VT (UT already planned)


# --- The year page ----------------------------------------------------------------

def test_year_page_has_a_column_per_year_in_order(client):
    page = page_text(client, "/years")
    this_year = date.today().year
    positions = [page.index(f'data-year="{this_year + n}"') for n in range(3)]
    assert positions == sorted(positions)


def test_year_page_shows_trip_cards_in_their_year(app, client):
    next_year = date.today().year + 1
    trip_id = make_trip(app, "Four Corners", f"{next_year}-03-01", f"{next_year}-03-03", ["CO", "NM"])
    page = page_text(client, "/years")
    column = page.split(f'data-year="{next_year}"')[1].split('data-year="')[0]
    assert "Four Corners" in column
    assert f"{next_year}-03-01" in column
    assert "Colorado" in column and "New Mexico" in column
    assert f'href="/trips/{trip_id}/edit?return_to=years"' in column
    assert f'action="/trips/{trip_id}/delete"' in column


def test_year_page_shows_new_states_and_the_running_total(app, client):
    next_year = date.today().year + 1
    client.post("/visits/new", data={"state": "CO", "visit_date": "2024-07-04", "note": ""})
    make_trip(app, "Four Corners", f"{next_year}-03-01", f"{next_year}-03-03", ["CO", "NM"])
    page = page_text(client, "/years")
    assert f"By the end of {next_year}: 2 of 50" in page
    assert "New states: New Mexico" in page


def test_empty_year_says_so(client):
    assert "No trips planned this year." in page_text(client, "/years")


def test_each_year_has_a_plan_a_trip_link(client):
    next_year = date.today().year + 1
    page = client.get("/years").get_data(as_text=True)
    assert f'href="/trips/new?year={next_year}"' in page


def test_nav_links_to_years(client):
    assert 'href="/years"' in client.get("/states").get_data(as_text=True)


# --- "Plan a trip in YEAR" -----------------------------------------------------

def test_plan_in_a_future_year_limits_the_start_date_to_that_year(client):
    next_year = date.today().year + 1
    page = client.get(f"/trips/new?year={next_year}").get_data(as_text=True)
    assert f'min="{next_year}-01-01"' in page
    assert f'max="{next_year}-12-31"' in page
    assert f"Plan a trip in {next_year}" in page


def test_plan_in_this_year_still_starts_tomorrow_at_the_earliest(client):
    this_year = date.today().year
    page = client.get(f"/trips/new?year={this_year}").get_data(as_text=True)
    assert f'min="{days_from_now(1)}"' in page
    assert f'max="{this_year}-12-31"' in page


def test_past_or_bad_year_is_ignored(client):
    for url in ("/trips/new?year=1999", "/trips/new?year=banana"):
        page = client.get(url).get_data(as_text=True)
        assert 'max="' not in page
        assert "<h1>Plan a trip</h1>" in page


def test_saving_a_trip_planned_from_the_year_page_goes_back_there(client):
    response = client.post(
        "/trips/new",
        data={
            "name": "Weekend", "start_date": days_from_now(7), "end_date": days_from_now(8),
            "states": ["VT"], "return_to": "years",
        },
    )
    assert response.headers["Location"].endswith("/years")


# --- Coming back to the year page after edit and delete --------------------------

def test_edit_from_the_year_page_goes_back_there(app, client):
    trip_id = make_trip(app, "Weekend", days_from_now(7), days_from_now(8), ["VT"])
    form = client.get(f"/trips/{trip_id}/edit?return_to=years").get_data(as_text=True)
    assert 'name="return_to" value="years"' in form
    response = client.post(
        f"/trips/{trip_id}/edit",
        data={
            "name": "Renamed", "start_date": days_from_now(7), "end_date": days_from_now(8),
            "states": ["VT"], "return_to": "years",
        },
    )
    assert response.headers["Location"].endswith("/years")


def test_delete_from_the_year_page_goes_back_there(app, client):
    trip_id = make_trip(app, "Weekend", days_from_now(7), days_from_now(8), ["VT"])
    response = client.post(f"/trips/{trip_id}/delete", data={"return_to": "years"})
    assert response.headers["Location"].endswith("/years")


def test_return_to_only_allows_pages_of_this_app(app, client):
    """Anything other than "years" goes to /trips, so a link can't send you to another website."""
    trip_id = make_trip(app, "Weekend", days_from_now(7), days_from_now(8), ["VT"])
    response = client.post(f"/trips/{trip_id}/delete", data={"return_to": "https://example.com"})
    assert response.headers["Location"].endswith("/trips")
    assert re.search(r"example\.com", response.headers["Location"]) is None
