"""Slice 13: an optional city on visits, and cities on planned trips."""
import json
import sqlite3
from datetime import date, timedelta
from html import unescape

from tracker import create_app
from tracker.db import get_db
from tracker.models import add_trip
from tracker.validation import validate_trip_cities, validate_visit

TODAY = date(2026, 10, 20)


def days_from_now(days):
    """Helper: a real date relative to today, as "YYYY-MM-DD", for the page tests."""
    return (date.today() + timedelta(days=days)).isoformat()


def page_text(client, url):
    """Helper: fetch a page and return its text as the browser would show it."""
    return unescape(client.get(url).get_data(as_text=True))


def post_visit(client, state="CO", city="", visit_date="2024-07-04", note=""):
    """Helper: submit the add-visit form."""
    return client.post(
        "/visits/new", data={"state": state, "city": city, "visit_date": visit_date, "note": note}
    )


def saved_visit_cities(app):
    """Helper: the city of every saved visit, oldest first."""
    with app.app_context():
        return [row[0] for row in get_db().execute("SELECT city FROM visits ORDER BY id")]


def post_trip(client, cities, states=("CO", "NM"), name="Four Corners", url="/trips/new"):
    """Helper: submit the trip form (new or edit) with a list of city lines."""
    return client.post(url, data={
        "name": name, "start_date": days_from_now(7), "end_date": days_from_now(9),
        "states": list(states), "cities": list(cities),
    })


def saved_trip_cities(app, trip_id=1):
    """Helper: a trip's cities as "City, ST" text, A to Z."""
    with app.app_context():
        rows = get_db().execute(
            "SELECT trip_cities.city, states.code FROM trip_cities"
            " JOIN states ON states.id = trip_cities.state_id"
            " WHERE trip_id = ? ORDER BY trip_cities.city", (trip_id,)
        )
        return [f"{city}, {code}" for city, code in rows]


# --- Updating a database made before cities existed (a "migration") ------------------

def test_old_database_gets_the_city_column_and_keeps_its_visits(tmp_path):
    """Your real database was created before cities existed. Starting the app must
    add what's missing without losing anything."""
    path = tmp_path / "old.sqlite"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE states (id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT UNIQUE NOT NULL);
        INSERT INTO states (code, name) VALUES ('CO', 'Colorado');
        CREATE TABLE visits (id INTEGER PRIMARY KEY, state_id INTEGER NOT NULL REFERENCES states(id),
                             visit_date TEXT NOT NULL, note TEXT NOT NULL DEFAULT '');
        INSERT INTO visits (state_id, visit_date, note) VALUES (1, '2024-07-04', 'old visit');
    """)
    old.commit()
    old.close()

    app = create_app({"TESTING": True, "DATABASE": str(path)})
    with app.app_context():
        db = get_db()
        columns = [row["name"] for row in db.execute("PRAGMA table_info(visits)")]
        visit = db.execute("SELECT note, city FROM visits").fetchone()
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    assert "city" in columns
    assert tuple(visit) == ("old visit", None)
    assert "trip_cities" in tables


# --- The city rules, checked directly ---------------------------------------------

def test_visit_city_is_optional():
    assert validate_visit("CO", "2024-07-04", TODAY, city="") == []


def test_visit_city_must_be_in_the_chosen_state():
    assert validate_visit("CO", "2024-07-04", TODAY, city="Denver") == []
    assert "We couldn't find “Denvr” in Colorado." in validate_visit("CO", "2024-07-04", TODAY, city="Denvr")
    assert "We couldn't find “Seattle” in Colorado." in validate_visit("CO", "2024-07-04", TODAY, city="Seattle")


def test_trip_cities_are_read_as_city_comma_state():
    errors, cities = validate_trip_cities(["Denver, CO", " santa fe , nm ", ""], ["CO", "NM"])
    assert errors == []
    assert cities == [("Denver", "CO"), ("Santa Fe", "NM")]  # official spelling, blanks skipped


def test_trip_city_must_be_written_with_its_state():
    errors, _ = validate_trip_cities(["Denver"], ["CO"])
    assert "Please write each city as “City, ST”, for example “Denver, CO”." in errors


def test_trip_city_must_exist():
    errors, _ = validate_trip_cities(["Denvr, CO"], ["CO"])
    assert "We couldn't find “Denvr, CO”." in errors


def test_trip_city_must_be_in_one_of_the_trips_states():
    errors, _ = validate_trip_cities(["Seattle, WA"], ["CO", "NM"])
    assert "Seattle, WA isn't in this trip's states." in errors


def test_trip_city_listed_twice_counts_once():
    errors, cities = validate_trip_cities(["Denver, CO", "denver, co"], ["CO"])
    assert (errors, cities) == ([], [("Denver", "CO")])


# --- City suggestions ---------------------------------------------------------------

def test_city_suggestions_for_a_state(client):
    """The forms fetch this list to suggest cities while you type."""
    response = client.get("/cities/CO")
    names = json.loads(response.get_data(as_text=True))
    assert "Denver" in names
    assert names == sorted(names, key=str.lower)
    assert client.get("/cities/co").status_code == 200
    assert client.get("/cities/DC").status_code == 404


# --- The visit form ----------------------------------------------------------------

def test_visit_form_has_an_optional_city_field_with_suggestions(client):
    page = client.get("/visits/new?state=CO").get_data(as_text=True)
    assert '<input type="text" name="city"' in page
    assert 'list="city-options"' in page
    assert '<datalist id="city-options">' in page
    assert '<option value="Denver">' in page
    assert 'src="/static/cities.js"' in page


def test_visit_with_a_city_is_saved_with_the_official_spelling(app, client):
    response = post_visit(client, city="  denver ")
    assert response.status_code == 302
    assert saved_visit_cities(app) == ["Denver"]


def test_visit_without_a_city_is_still_fine(app, client):
    assert post_visit(client, city="").status_code == 302
    assert saved_visit_cities(app) == [None]


def test_visit_with_an_unknown_city_is_not_saved(app, client):
    response = post_visit(client, city="Denvr")
    assert response.status_code == 400
    assert "We couldn't find “Denvr” in Colorado." in unescape(response.get_data(as_text=True))
    assert 'value="Denvr"' in response.get_data(as_text=True)  # you don't have to type it again
    assert saved_visit_cities(app) == []


def test_two_visits_with_cities_in_one_state_still_count_once(client):
    """Cities don't change the progress: it still counts states."""
    post_visit(client, city="Denver")
    post_visit(client, city="Boulder", visit_date="2025-01-02")
    assert "1 of 50" in page_text(client, "/states")


def test_state_page_shows_the_city_of_each_visit(client):
    post_visit(client, city="Denver", note="Red Rocks")
    page = page_text(client, "/states/CO")
    assert "Denver" in page and "Red Rocks" in page


# --- The trip form -------------------------------------------------------------------

def test_trip_form_has_three_city_rows_and_an_add_button(client):
    page = client.get("/trips/new").get_data(as_text=True)
    assert page.count('name="cities"') == 3
    assert "Add another city" in page
    assert 'src="/static/cities.js"' in page


def test_trip_with_cities_is_saved(app, client):
    response = post_trip(client, ["denver, co", "Santa Fe, NM", ""])
    assert response.status_code == 302
    assert saved_trip_cities(app) == ["Denver, CO", "Santa Fe, NM"]


def test_trip_with_a_bad_city_is_not_saved_and_keeps_what_you_typed(app, client):
    response = post_trip(client, ["Denver, CO", "Seattle, WA"])
    assert response.status_code == 400
    page = unescape(response.get_data(as_text=True))
    assert "Seattle, WA isn't in this trip's states." in page
    assert 'value="Denver, CO"' in page and 'value="Seattle, WA"' in page
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM trips").fetchone()[0] == 0


def test_edit_form_shows_the_trips_cities(app, client):
    post_trip(client, ["Denver, CO", "Santa Fe, NM"])
    page = client.get("/trips/1/edit").get_data(as_text=True)
    assert 'value="Denver, CO"' in page
    assert 'value="Santa Fe, NM"' in page
    assert page.count('name="cities"') >= 3  # always room for one more


def test_editing_replaces_the_cities(app, client):
    post_trip(client, ["Denver, CO", "Santa Fe, NM"])
    post_trip(client, ["Boulder, CO"], url="/trips/1/edit")
    assert saved_trip_cities(app) == ["Boulder, CO"]


def test_deleting_a_trip_removes_its_cities(app, client):
    post_trip(client, ["Denver, CO"])
    client.post("/trips/1/delete")
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM trip_cities").fetchone()[0] == 0


def test_moving_a_trip_keeps_its_cities(app, client):
    with app.app_context():
        trip_id = add_trip("Fall", f"{date.today().year + 1}-10-02", f"{date.today().year + 1}-10-04",
                           ["CO"], cities=[("Denver", "CO")])
    client.post(f"/trips/{trip_id}/move", data={"year": date.today().year + 2})
    assert saved_trip_cities(app, trip_id) == ["Denver, CO"]


def test_trip_cities_show_on_the_trips_page_and_their_state_page(client):
    post_trip(client, ["Denver, CO", "Santa Fe, NM"])
    assert "Denver, CO" in page_text(client, "/trips")
    colorado = page_text(client, "/states/CO")
    assert "Denver" in colorado and "Santa Fe" not in colorado
    assert "Santa Fe" in page_text(client, "/states/NM")
