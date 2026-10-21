"""Slice 18: editing and deleting visits."""
from datetime import date, timedelta
from html import unescape

from tracker.db import get_db
from tracker.models import add_trip, add_visit


def days_from_now(days):
    """Helper: a real date relative to today, as "YYYY-MM-DD"."""
    return (date.today() + timedelta(days=days)).isoformat()


def make_visit(app, state="CO", visit_date="2024-07-04", note="Red Rocks", city="Denver"):
    """Helper: save a visit directly and return its id."""
    with app.app_context():
        return add_visit(state, visit_date, note, city)


def visit_in_db(app, visit_id):
    """Helper: (state code, date, note, city) of one visit, or None if it's gone."""
    with app.app_context():
        row = get_db().execute(
            "SELECT states.code, visit_date, note, city FROM visits"
            " JOIN states ON states.id = visits.state_id WHERE visits.id = ?",
            (visit_id,),
        ).fetchone()
    return tuple(row) if row else None


def post_edit(client, visit_id, state="CO", visit_date="2025-03-01", note="Coors Field", city="Boulder"):
    """Helper: submit the edit form. By default, valid new values."""
    return client.post(
        f"/visits/{visit_id}/edit",
        data={"state": state, "visit_date": visit_date, "note": note, "city": city},
    )


def page_text(client, url):
    """Helper: fetch a page and return its text as the browser would show it."""
    return unescape(client.get(url).get_data(as_text=True))


# --- Editing -------------------------------------------------------------------------

def test_edit_form_is_filled_in_with_the_visit(app, client):
    visit_id = make_visit(app)
    page = client.get(f"/visits/{visit_id}/edit").get_data(as_text=True)
    assert "<h1>Edit visit</h1>" in page
    assert '<option value="CO" selected' in page
    assert 'value="2024-07-04"' in page
    assert 'value="Denver"' in page
    assert 'value="Red Rocks"' in page
    assert "Save changes" in page
    assert '<option value="Boulder">' in page  # city suggestions for the visit's state


def test_editing_changes_date_note_and_city(app, client):
    visit_id = make_visit(app)
    response = post_edit(client, visit_id, city="boulder")
    # After saving, you land on the visit's state page.
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/states/CO")
    assert visit_in_db(app, visit_id) == ("CO", "2025-03-01", "Coors Field", "Boulder")


def test_editing_can_add_a_city_to_a_visit_without_one(app, client):
    visit_id = make_visit(app, city=None)
    post_edit(client, visit_id, city="Denver")
    assert visit_in_db(app, visit_id)[3] == "Denver"


def test_editing_can_remove_the_city(app, client):
    visit_id = make_visit(app)
    post_edit(client, visit_id, city="")
    assert visit_in_db(app, visit_id)[3] is None


def test_editing_can_move_a_visit_to_another_state(app, client):
    visit_id = make_visit(app)
    response = post_edit(client, visit_id, state="UT", city="Moab")
    assert response.headers["Location"].endswith("/states/UT")
    assert visit_in_db(app, visit_id)[:1] + visit_in_db(app, visit_id)[3:] == ("UT", "Moab")


def test_city_must_be_in_the_new_state(app, client):
    """Denver is in Colorado, not Utah."""
    visit_id = make_visit(app)
    response = post_edit(client, visit_id, state="UT", city="Denver")
    assert response.status_code == 400
    assert "We couldn't find “Denver” in Utah." in unescape(response.get_data(as_text=True))
    assert visit_in_db(app, visit_id) == ("CO", "2024-07-04", "Red Rocks", "Denver")


def test_future_date_is_refused_and_nothing_changes(app, client):
    visit_id = make_visit(app)
    response = post_edit(client, visit_id, visit_date=days_from_now(1), note="typed note")
    assert response.status_code == 400
    page = unescape(response.get_data(as_text=True))
    assert "The visit date can't be in the future." in page
    assert 'value="typed note"' in page  # keeps what you typed
    assert visit_in_db(app, visit_id) == ("CO", "2024-07-04", "Red Rocks", "Denver")


def test_editing_an_unknown_visit_gives_404(client):
    assert client.get("/visits/999/edit").status_code == 404
    assert post_edit(client, 999).status_code == 404


# --- Deleting ------------------------------------------------------------------------

def test_deleting_removes_only_that_visit(app, client):
    first = make_visit(app)
    second = make_visit(app, visit_date="2025-03-01", city="Boulder")
    response = client.post(f"/visits/{first}/delete")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/states/CO")
    assert visit_in_db(app, first) is None
    assert visit_in_db(app, second) is not None


def test_delete_only_works_by_submitting_the_form(app, client):
    """Just opening the address (a GET) gives 405 and deletes nothing."""
    visit_id = make_visit(app)
    assert client.get(f"/visits/{visit_id}/delete").status_code == 405
    assert visit_in_db(app, visit_id) is not None


def test_deleting_an_unknown_visit_gives_404(client):
    assert client.post("/visits/999/delete").status_code == 404


def test_state_page_has_edit_and_delete_for_each_visit(app, client):
    visit_id = make_visit(app)
    page = client.get("/states/CO").get_data(as_text=True)
    assert f'href="/visits/{visit_id}/edit"' in page
    assert f'action="/visits/{visit_id}/delete"' in page
    assert "confirm(" in unescape(page)


# --- Every page follows ------------------------------------------------------------------

def test_deleting_the_only_visit_makes_the_state_unvisited_again(app, client):
    visit_id = make_visit(app)
    assert "1 of 50" in page_text(client, "/states")
    client.post(f"/visits/{visit_id}/delete")
    assert "0 of 50" in page_text(client, "/states")
    assert 'id="state-CO" class="state unvisited"' in client.get("/map").get_data(as_text=True)
    west = page_text(client, "/map").split('data-region="West"')[1].split("</article>")[0]
    assert '<span class="region-count">0 of 13</span>' in west


def test_deleting_one_of_two_visits_keeps_the_state_visited(app, client):
    first = make_visit(app)
    make_visit(app, visit_date="2025-03-01", city="Boulder")
    client.post(f"/visits/{first}/delete")
    assert "1 of 50" in page_text(client, "/states")
    assert 'id="state-CO" class="state visited"' in client.get("/map").get_data(as_text=True)


def test_deleting_the_last_visit_to_a_city_removes_its_dot(app, client):
    visit_id = make_visit(app)
    client.post(f"/visits/{visit_id}/delete")
    assert 'data-city="Denver, CO"' not in client.get("/map").get_data(as_text=True)


def test_a_city_still_in_an_upcoming_trip_keeps_a_blue_dot(app, client):
    visit_id = make_visit(app)
    with app.app_context():
        add_trip("Back to Denver", days_from_now(7), days_from_now(9), ["CO"], cities=[("Denver", "CO")])
    client.post(f"/visits/{visit_id}/delete")
    assert '<circle class="city-dot upcoming" data-city="Denver, CO"' in client.get("/map").get_data(as_text=True)


def test_moving_a_visit_moves_it_on_the_map_and_in_the_counts(app, client):
    visit_id = make_visit(app)
    post_edit(client, visit_id, state="UT", city="Moab")
    page = client.get("/map").get_data(as_text=True)
    assert 'id="state-CO" class="state unvisited"' in page
    assert 'id="state-UT" class="state visited"' in page
    assert 'data-city="Moab, UT"' in page and 'data-city="Denver, CO"' not in page
    assert "1 of 50" in page_text(client, "/states")
