"""Slice 16: region cards on phones, instead of the map."""
import re
from datetime import date, timedelta
from html import unescape

from tracker.models import add_trip, add_visit, get_next_trip, get_regions
from tracker.regions_data import REGIONS
from tests.test_states import EXPECTED_STATES

TODAY = date(2026, 10, 20)


def days_from(day, days):
    """Helper: a date `days` after `day`, as "YYYY-MM-DD"."""
    return (day + timedelta(days=days)).isoformat()


def visit(app, state, city=None, visit_date="2024-07-04"):
    """Helper: save a visit (optionally with a city)."""
    with app.app_context():
        add_visit(state, visit_date, "", city)


def trip(app, states, start, end, name="Weekend", cities=()):
    """Helper: save a trip directly, so tests can also make past trips."""
    with app.app_context():
        return add_trip(name, start, end, list(states), cities=list(cities))


def regions(app, today=TODAY, year=None):
    """Helper: get_regions() as {"West": region}."""
    with app.app_context():
        return {region["name"]: region for region in get_regions(today, year=year)}


def chip(region, code):
    """Helper: one state's chip in a region."""
    return next(state for state in region["states"] if state["code"] == code)


def map_page(client, url="/map"):
    """Helper: the map page as text, as the browser would show it."""
    return unescape(client.get(url).get_data(as_text=True))


def css():
    """Helper: the stylesheet as text."""
    with open("tracker/static/style.css") as f:
        return f.read()


# --- The regions themselves -----------------------------------------------------------

def test_the_four_census_regions_cover_all_50_states_once():
    codes = [code for name, states in REGIONS for code in states]
    assert sorted(codes) == sorted(EXPECTED_STATES)  # every state, none twice, no DC
    assert [(name, len(states)) for name, states in REGIONS] == [
        ("Northeast", 9), ("Midwest", 12), ("South", 16), ("West", 13),
    ]


def test_regions_list_their_states_a_to_z_with_full_names(app):
    west = regions(app)["West"]
    names = [state["name"] for state in west["states"]]
    assert names == sorted(names)
    assert "California" in names and "Hawaii" in names


# --- Counting -------------------------------------------------------------------------

def test_empty_database_has_nothing_visited_or_planned(app):
    for region in regions(app).values():
        assert (region["visited"], region["planned"]) == (0, 0)
        assert region["total"] == len(region["states"])


def test_visits_and_trips_are_counted_per_region(app):
    visit(app, "CA")
    trip(app, ["OR"], days_from(TODAY, 7), days_from(TODAY, 9))
    west = regions(app)["West"]
    assert (west["visited"], west["planned"], west["total"]) == (1, 1, 13)
    assert chip(west, "CA")["status"] == "visited"
    assert chip(west, "OR")["status"] == "planned"
    assert chip(west, "WA")["status"] == "unvisited"
    assert regions(app)["South"]["visited"] == 0


def test_visited_and_planned_counts_as_visited(app):
    visit(app, "CA")
    trip(app, ["CA"], days_from(TODAY, 7), days_from(TODAY, 9))
    west = regions(app)["West"]
    assert (west["visited"], west["planned"]) == (1, 0)


def test_a_trip_that_has_ended_is_not_planned(app):
    trip(app, ["OR"], "2025-06-01", "2025-06-03")
    assert regions(app)["West"]["planned"] == 0


def test_year_filter_changes_what_counts_as_planned(app):
    trip(app, ["OR"], "2027-04-02", "2027-04-05")
    assert regions(app, year=2026)["West"]["planned"] == 0
    assert regions(app, year=2027)["West"]["planned"] == 1


def test_city_badge_counts_visited_cities(app):
    """Two visits to Denver and one to Boulder: 2 cities in Colorado."""
    visit(app, "CO", "Denver", "2024-07-04")
    visit(app, "CO", "Denver", "2025-03-01")
    visit(app, "CO", "Boulder", "2025-03-02")
    trip(app, ["CO"], days_from(TODAY, 7), days_from(TODAY, 9), cities=[("Aspen", "CO")])
    assert chip(regions(app)["West"], "CO")["city_count"] == 2  # Aspen isn't visited yet


# --- The next trip ------------------------------------------------------------------------

def test_next_trip_is_the_soonest_one(app):
    trip(app, ["OR"], days_from(TODAY, 30), days_from(TODAY, 31), name="Later")
    trip(app, ["TX"], days_from(TODAY, 10), days_from(TODAY, 12), name="Sooner")
    with app.app_context():
        nxt = get_next_trip(TODAY)
    assert (nxt["name"], nxt["when"]) == ("Sooner", "in 10 days")


def test_next_trip_tomorrow_and_happening_now(app):
    trip(app, ["TX"], days_from(TODAY, 1), days_from(TODAY, 2), name="Tomorrow")
    with app.app_context():
        assert get_next_trip(TODAY)["when"] == "tomorrow"
    trip(app, ["OR"], days_from(TODAY, -1), days_from(TODAY, 1), name="Now")
    with app.app_context():
        nxt = get_next_trip(TODAY)
    assert (nxt["name"], nxt["when"]) == ("Now", "happening now")


def test_no_next_trip_when_nothing_is_planned_or_everything_ended(app):
    trip(app, ["OR"], "2025-06-01", "2025-06-03")
    with app.app_context():
        assert get_next_trip(TODAY) is None


# --- The page ---------------------------------------------------------------------------

def test_map_page_has_both_views(client):
    page = map_page(client)
    assert '<div class="map-view">' in page
    assert '<section class="region-view">' in page


def test_region_cards_show_name_count_bar_and_chips(app, client):
    visit(app, "CA", "San Diego")
    page = map_page(client)
    card = page.split('<article class="region-card" data-region="West">')[1].split("</article>")[0]
    assert "<h2>West</h2>" in card
    assert '<span class="region-count">1 of 13</span>' in card
    assert '<span class="bar-visited" style="width: 7.7%"></span>' in card  # 1 of 13
    assert re.search(r'<a class="state-chip visited" href="/states/CA">California\s*<span class="chip-count">1</span>', card)
    assert '<a class="state-chip unvisited" href="/states/WA">Washington' in card


def test_every_state_has_a_chip_linking_to_its_page(client):
    page = map_page(client)
    for code in EXPECTED_STATES:
        assert re.search(rf'<a class="state-chip \w+" href="/states/{code}">', page), code


def test_next_trip_card(app, client):
    trip(app, ["TX"], days_from(date.today(), 10), days_from(date.today(), 12),
         name="Texas weekend", cities=[("Austin", "TX")])
    page = map_page(client)
    card = page.split('<section class="next-trip">')[1].split("</section>")[0]
    assert "Next trip · in 10 days" in card
    assert "Texas weekend" in card
    assert "Texas" in card and "Austin" in card
    assert 'href="/trips"' in card


def test_next_trip_card_without_trips_offers_to_plan_one(client):
    card = map_page(client).split('<section class="next-trip">')[1].split("</section>")[0]
    assert "No trips planned yet." in card
    assert 'href="/trips/new"' in card


def test_year_filter_links_appear_in_the_region_view_too(app, client):
    trip(app, ["OR"], f"{date.today().year + 1}-04-02", f"{date.today().year + 1}-04-05")
    view = map_page(client).split('<section class="region-view">')[1]
    assert f'href="/map?year={date.today().year + 1}"' in view


# --- Which view shows on which screen ---------------------------------------------------

def test_phones_get_the_cards_and_bigger_screens_the_map():
    """The region view is hidden by default; at 640px or less it replaces the map."""
    assert re.search(r"\.region-view \{\s*display: none;", css())
    phone = re.search(r"@media \(max-width: 640px\) \{(.*?)(?=\n@media|\Z)", css(), re.S).group(1)
    assert re.search(r"\.region-view \{\s*display: block;", phone)
    assert re.search(r"\.map-view \{\s*display: none;", phone)


def test_chips_are_big_enough_to_tap():
    rule = re.search(r"\.state-chip \{(.*?)\}", css(), re.S).group(1)
    assert "min-height: 44px" in rule


def test_the_default_comes_before_the_phone_rule():
    """With equally specific rules, the later one in the file wins. If "hide the
    cards" came after the phone rule, phones would see neither the cards nor the map."""
    text = css()
    default = re.search(r"\.region-view \{\s*display: none;", text).start()
    phone = text.index("@media (max-width: 640px)")
    assert default < phone
