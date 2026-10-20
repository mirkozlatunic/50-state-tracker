"""Slice 8: moving a trip to another year (by dragging, or with the "Move to" menu)."""
from datetime import date
from html import unescape

from tracker.db import get_db
from tracker.models import add_trip, shift_to_year

THIS_YEAR = date.today().year
NEXT_YEAR = THIS_YEAR + 1


def make_trip(app, name, start, end, states=("VT",)):
    """Helper: save a trip directly (skipping the form) and return its id."""
    with app.app_context():
        return add_trip(name, start, end, list(states))


def trip_dates(app, trip_id):
    """Helper: (start, end) of one trip as stored in the database."""
    with app.app_context():
        row = get_db().execute(
            "SELECT start_date, end_date FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
    return (row["start_date"], row["end_date"])


def move(client, trip_id, year):
    """Helper: submit the "Move to" form, which is what dropping a card does too."""
    return client.post(f"/trips/{trip_id}/move", data={"year": year})


def page_text(client, url):
    """Helper: fetch a page and return its text as the browser would show it."""
    return unescape(client.get(url).get_data(as_text=True))


# --- Working out the new dates ----------------------------------------------------

def test_shift_keeps_month_and_day():
    assert shift_to_year("2026-11-06", "2026-11-08", 2027) == (date(2027, 11, 6), date(2027, 11, 8))


def test_shift_works_backwards_too():
    assert shift_to_year("2028-05-01", "2028-05-03", 2027) == (date(2027, 5, 1), date(2027, 5, 3))


def test_shift_keeps_a_trip_across_new_year_the_same_length():
    """Dec 30 to Jan 2 is a 4-day trip, before and after the move."""
    assert shift_to_year("2026-12-30", "2027-01-02", 2027) == (date(2027, 12, 30), date(2028, 1, 2))


def test_shift_turns_feb_29_into_feb_28_in_a_normal_year():
    """2028 is a leap year, 2029 isn't. The trip keeps its length (3 days)."""
    assert shift_to_year("2028-02-29", "2028-03-02", 2029) == (date(2029, 2, 28), date(2029, 3, 2))


def test_shift_keeps_feb_29_in_a_leap_year():
    assert shift_to_year("2028-02-29", "2028-03-01", 2032) == (date(2032, 2, 29), date(2032, 3, 1))


# --- Moving a trip ------------------------------------------------------------------

def test_moving_a_trip_changes_its_dates(app, client):
    trip_id = make_trip(app, "Fall colors", f"{NEXT_YEAR}-10-02", f"{NEXT_YEAR}-10-04")
    response = move(client, trip_id, NEXT_YEAR + 1)
    # After moving, you're back on the year page.
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/years")
    assert trip_dates(app, trip_id) == (f"{NEXT_YEAR + 1}-10-02", f"{NEXT_YEAR + 1}-10-04")


def test_moving_to_the_same_year_changes_nothing(app, client):
    trip_id = make_trip(app, "Fall colors", f"{NEXT_YEAR}-10-02", f"{NEXT_YEAR}-10-04")
    assert move(client, trip_id, NEXT_YEAR).status_code == 302
    assert trip_dates(app, trip_id) == (f"{NEXT_YEAR}-10-02", f"{NEXT_YEAR}-10-04")


def test_moving_into_the_past_is_refused(app, client):
    """Jan 1 of this year has always passed by now (or is today), and a planned
    trip must start in the future. Nothing changes and the year page explains why."""
    trip_id = make_trip(app, "New Year's", f"{NEXT_YEAR}-01-01", f"{NEXT_YEAR}-01-02")
    response = move(client, trip_id, THIS_YEAR)
    assert response.status_code == 400
    page = unescape(response.get_data(as_text=True))
    assert "A planned trip must start in the future." in page
    assert "New Year's" in page  # still the year page, so you can try again
    assert trip_dates(app, trip_id) == (f"{NEXT_YEAR}-01-01", f"{NEXT_YEAR}-01-02")


def test_moving_to_a_bad_year_is_refused(app, client):
    trip_id = make_trip(app, "Fall colors", f"{NEXT_YEAR}-10-02", f"{NEXT_YEAR}-10-04")
    for bad in ("banana", "", "1999", "10000"):
        response = move(client, trip_id, bad)
        assert response.status_code == 400
        assert "Please choose a year from this year on." in unescape(response.get_data(as_text=True))
    assert trip_dates(app, trip_id) == (f"{NEXT_YEAR}-10-02", f"{NEXT_YEAR}-10-04")


def test_moving_an_unknown_trip_gives_404(client):
    assert move(client, 999, NEXT_YEAR).status_code == 404


def test_move_only_works_by_submitting_the_form(app, client):
    """Just opening the address (a GET) gives 405 and moves nothing."""
    trip_id = make_trip(app, "Fall colors", f"{NEXT_YEAR}-10-02", f"{NEXT_YEAR}-10-04")
    assert client.get(f"/trips/{trip_id}/move").status_code == 405


# --- The move shows up everywhere ---------------------------------------------------

def test_moved_trip_shows_in_its_new_year_column(app, client):
    trip_id = make_trip(app, "Fall colors", f"{NEXT_YEAR}-10-02", f"{NEXT_YEAR}-10-04")
    move(client, trip_id, NEXT_YEAR + 1)
    page = page_text(client, "/years")
    old_column = page.split(f'data-year="{NEXT_YEAR}"')[1].split('data-year="')[0]
    new_column = page.split(f'data-year="{NEXT_YEAR + 1}"')[1].split('data-year="')[0]
    assert "Fall colors" not in old_column
    assert "Fall colors" in new_column


def test_moved_trip_shows_new_dates_on_the_trips_page(app, client):
    trip_id = make_trip(app, "Fall colors", f"{NEXT_YEAR}-10-02", f"{NEXT_YEAR}-10-04")
    move(client, trip_id, NEXT_YEAR + 1)
    assert f"{NEXT_YEAR + 1}-10-02 to {NEXT_YEAR + 1}-10-04" in page_text(client, "/trips")


def test_moved_trip_follows_the_map_year_filter(app, client):
    trip_id = make_trip(app, "Fall colors", f"{NEXT_YEAR}-10-02", f"{NEXT_YEAR}-10-04", states=("VT",))
    move(client, trip_id, NEXT_YEAR + 1)
    assert 'id="state-VT" class="state unvisited"' in client.get(f"/map?year={NEXT_YEAR}").get_data(as_text=True)
    assert 'id="state-VT" class="state planned"' in client.get(f"/map?year={NEXT_YEAR + 1}").get_data(as_text=True)


# --- What the year page offers -------------------------------------------------------

def test_each_card_has_a_move_to_menu_with_the_other_years(app, client):
    """The menu works without JavaScript, e.g. with a keyboard or on a phone."""
    trip_id = make_trip(app, "Fall colors", f"{NEXT_YEAR}-10-02", f"{NEXT_YEAR}-10-04")
    page = client.get("/years").get_data(as_text=True)
    card = page.split(f'data-trip-id="{trip_id}"')[1].split("</article>")[0]
    assert f'action="/trips/{trip_id}/move"' in card
    assert f'<option value="{THIS_YEAR}">' in card
    assert f'<option value="{NEXT_YEAR + 1}">' in card
    assert f'<option value="{NEXT_YEAR}">' not in card  # the year it's already in


def test_cards_can_be_dragged(app, client):
    make_trip(app, "Fall colors", f"{NEXT_YEAR}-10-02", f"{NEXT_YEAR}-10-04")
    page = client.get("/years").get_data(as_text=True)
    assert 'draggable="true"' in page
    assert 'src="/static/years.js"' in page


def test_drag_script_exists(client):
    response = client.get("/static/years.js")
    assert response.status_code == 200
    assert "drop" in response.get_data(as_text=True)
