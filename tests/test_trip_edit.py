"""Slice 5: editing and deleting planned trips."""
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


def make_trip(app, name="Four Corners weekend", start=7, end=9, states=("AZ", "UT")):
    """Helper: save a trip directly (skipping the form) and return its id.

    `start` and `end` are days from today, so start=-1 means "started yesterday".
    """
    with app.app_context():
        return add_trip(name, days_from_now(start), days_from_now(end), list(states))


def trip_in_db(app, trip_id):
    """Helper: (name, start, end, [state codes]) for one trip, or None if it's gone."""
    with app.app_context():
        db = get_db()
        row = db.execute(
            "SELECT name, start_date, end_date FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        if row is None:
            return None
        codes = [r[0] for r in db.execute(
            "SELECT states.code FROM trip_states JOIN states ON states.id = trip_states.state_id"
            " WHERE trip_id = ? ORDER BY states.code",
            (trip_id,),
        )]
    return (row["name"], row["start_date"], row["end_date"], codes)


def post_edit(client, trip_id, name="Renamed trip", start=None, end=None, states=("CO", "NM")):
    """Helper: submit the edit form. By default, valid new values two weeks out."""
    return client.post(
        f"/trips/{trip_id}/edit",
        data={
            "name": name,
            "start_date": start if start is not None else days_from_now(14),
            "end_date": end if end is not None else days_from_now(16),
            "states": list(states),
        },
    )


def page_text(client, url):
    """Helper: fetch a page and return its text as the browser would show it."""
    return unescape(client.get(url).get_data(as_text=True))


# --- The rule for keeping a start date, checked directly ---------------------

def test_editing_may_keep_a_start_date_that_has_passed():
    """A trip that started yesterday can still be renamed without moving its start."""
    errors = validate_trip("Weekend", "2026-10-19", "2026-10-22", ["AZ"], TODAY, keep_start="2026-10-19")
    assert errors == []


def test_editing_may_not_move_the_start_to_another_past_date():
    errors = validate_trip("Weekend", "2026-10-18", "2026-10-22", ["AZ"], TODAY, keep_start="2026-10-19")
    assert "A planned trip must start in the future." in errors


def test_editing_may_move_the_start_into_the_future():
    errors = validate_trip("Weekend", "2026-11-01", "2026-11-02", ["AZ"], TODAY, keep_start="2026-10-19")
    assert errors == []


def test_kept_start_date_still_needs_end_not_before_start():
    errors = validate_trip("Weekend", "2026-10-19", "2026-10-18", ["AZ"], TODAY, keep_start="2026-10-19")
    assert "The end date can't be before the start date." in errors


# --- Editing -----------------------------------------------------------------

def test_edit_form_is_filled_in_with_the_trip(app, client):
    trip_id = make_trip(app)
    page = client.get(f"/trips/{trip_id}/edit").get_data(as_text=True)
    assert 'value="Four Corners weekend"' in page
    assert f'value="{days_from_now(7)}"' in page
    assert f'value="{days_from_now(9)}"' in page
    assert 'value="AZ" checked' in page
    assert 'value="UT" checked' in page
    assert 'value="CA" checked' not in page
    assert "Save changes" in page


def test_editing_changes_name_dates_and_states(app, client):
    trip_id = make_trip(app)
    response = post_edit(client, trip_id)
    # After saving, you're sent to the trips list.
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/trips")
    assert trip_in_db(app, trip_id) == (
        "Renamed trip", days_from_now(14), days_from_now(16), ["CO", "NM"]
    )


def test_bad_edit_shows_an_error_and_changes_nothing(app, client):
    trip_id = make_trip(app)
    before = trip_in_db(app, trip_id)
    response = post_edit(client, trip_id, start=days_from_now(14), end=days_from_now(13))
    assert response.status_code == 400
    assert "The end date can't be before the start date." in unescape(response.get_data(as_text=True))
    assert trip_in_db(app, trip_id) == before


def test_trip_in_progress_can_be_renamed(app, client):
    trip_id = make_trip(app, start=-1, end=1)
    response = post_edit(
        client, trip_id, name="Still going", start=days_from_now(-1), end=days_from_now(1), states=("AZ",)
    )
    assert response.status_code == 302
    assert trip_in_db(app, trip_id)[0] == "Still going"


def test_trip_in_progress_cannot_move_to_another_past_date(app, client):
    trip_id = make_trip(app, start=-1, end=1)
    response = post_edit(client, trip_id, start=days_from_now(-2), end=days_from_now(1))
    assert response.status_code == 400
    assert trip_in_db(app, trip_id)[1] == days_from_now(-1)


def test_edit_shows_on_the_trips_page_and_state_pages(app, client):
    """Changes are reflected everywhere, because every page reads the same tables."""
    trip_id = make_trip(app, name="Four Corners weekend", states=("AZ", "UT"))
    post_edit(client, trip_id, name="Rockies weekend", states=("CO",))
    assert "Rockies weekend" in page_text(client, "/trips")
    assert "Four Corners weekend" not in page_text(client, "/trips")
    assert "Rockies weekend" in page_text(client, "/states/CO")
    assert "Rockies weekend" not in page_text(client, "/states/AZ")


def test_editing_an_unknown_trip_gives_404(client):
    assert client.get("/trips/999/edit").status_code == 404
    assert post_edit(client, 999).status_code == 404


# --- Deleting ----------------------------------------------------------------

def test_deleting_a_trip_removes_it_and_its_states(app, client):
    trip_id = make_trip(app)
    response = client.post(f"/trips/{trip_id}/delete")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/trips")
    assert trip_in_db(app, trip_id) is None
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM trip_states").fetchone()[0] == 0


def test_deleting_a_trip_keeps_visits(app, client):
    client.post("/visits/new", data={"state": "AZ", "visit_date": "2024-07-04", "note": ""})
    trip_id = make_trip(app, states=("AZ",))
    client.post(f"/trips/{trip_id}/delete")
    assert "1 of 50" in page_text(client, "/states")


def test_deleted_trip_is_gone_from_every_page(app, client):
    trip_id = make_trip(app, name="Four Corners weekend", states=("AZ",))
    client.post(f"/trips/{trip_id}/delete")
    assert "Four Corners weekend" not in page_text(client, "/trips")
    assert "Four Corners weekend" not in page_text(client, "/states/AZ")


def test_delete_only_works_by_submitting_the_form(app, client):
    """Opening the delete address in the browser (a GET) must not delete anything.

    405 means "Method Not Allowed": that address only accepts a submitted form (POST).
    """
    trip_id = make_trip(app)
    assert client.get(f"/trips/{trip_id}/delete").status_code == 405
    assert trip_in_db(app, trip_id) is not None


def test_deleting_an_unknown_trip_gives_404(client):
    assert client.post("/trips/999/delete").status_code == 404


# --- Buttons on the trips page -----------------------------------------------

def test_trips_page_has_edit_and_delete_for_each_trip(app, client):
    trip_id = make_trip(app)
    page = client.get("/trips").get_data(as_text=True)
    assert f'href="/trips/{trip_id}/edit"' in page
    assert f'action="/trips/{trip_id}/delete"' in page


def test_delete_asks_are_you_sure(app, client):
    make_trip(app)
    page = unescape(client.get("/trips").get_data(as_text=True))
    assert "confirm(" in page
