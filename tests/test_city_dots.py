"""Slice 14: a dot on the map for every visited city and every upcoming trip city."""
import re
from datetime import date, timedelta
from html import unescape

from tracker.cities import find_city
from tracker.models import add_trip, add_visit, get_city_dots

THIS_YEAR = date.today().year
NEXT_YEAR = THIS_YEAR + 1


def days_from_now(days):
    """Helper: a real date relative to today, as "YYYY-MM-DD"."""
    return (date.today() + timedelta(days=days)).isoformat()


def visit(app, city, state="CO", visit_date="2024-07-04"):
    """Helper: save a visit with a city."""
    with app.app_context():
        add_visit(state, visit_date, "", city)


def trip(app, cities, start=None, end=None, name="Four Corners weekend"):
    """Helper: save a trip with cities, e.g. [("Denver", "CO")]. Default: next week."""
    states = sorted({code for _, code in cities})
    with app.app_context():
        return add_trip(name, start or days_from_now(7), end or days_from_now(9), states, cities=cities)


def dots(app, year=None):
    """Helper: get_city_dots() as {"Denver, CO": dot}."""
    with app.app_context():
        return {f"{d['name']}, {d['state']}": d for d in get_city_dots(date.today(), year=year)}


def map_page(client, url="/map"):
    """Helper: the map page as HTML text."""
    return client.get(url).get_data(as_text=True)


# --- Which cities get a dot, and which kind -------------------------------------------

def test_no_cities_no_dots(app, client):
    client.post("/visits/new", data={"state": "CO", "visit_date": "2024-07-04", "note": ""})
    assert dots(app) == {}
    assert 'class="city-dot' not in map_page(client)


def test_visited_city_gets_a_visited_dot_at_the_city(app):
    visit(app, "Denver")
    dot = dots(app)["Denver, CO"]
    denver = find_city("Denver", "CO")
    assert dot["kind"] == "visited"
    assert (dot["x"], dot["y"]) == (denver.x, denver.y)


def test_city_in_an_upcoming_trip_gets_an_upcoming_dot(app):
    trip(app, [("Santa Fe", "NM")])
    assert dots(app)["Santa Fe, NM"]["kind"] == "upcoming"


def test_city_visited_and_upcoming_shows_as_upcoming(app):
    """Your choice: the upcoming color wins, so you see you're going back."""
    visit(app, "Denver")
    trip(app, [("Denver", "CO")])
    dot = dots(app)["Denver, CO"]
    assert dot["kind"] == "upcoming"
    assert dot["visit_dates"] == ["2024-07-04"]
    assert dot["trips"] == [("Four Corners weekend", days_from_now(7))]


def test_city_from_a_trip_that_ended_gets_no_dot(app):
    trip(app, [("Portland", "OR")], start="2025-06-01", end="2025-06-03")
    assert "Portland, OR" not in dots(app)


def test_two_visits_to_a_city_give_one_dot_with_both_dates(app):
    visit(app, "Denver", visit_date="2025-03-01")
    visit(app, "Denver", visit_date="2024-07-04")
    result = dots(app)
    assert list(result) == ["Denver, CO"]
    assert result["Denver, CO"]["visit_dates"] == ["2024-07-04", "2025-03-01"]  # oldest first


def test_year_filter_applies_to_upcoming_dots(app):
    trip(app, [("Santa Fe", "NM")], start=f"{NEXT_YEAR}-04-02", end=f"{NEXT_YEAR}-04-05")
    assert "Santa Fe, NM" not in dots(app, year=THIS_YEAR)
    assert dots(app, year=NEXT_YEAR)["Santa Fe, NM"]["kind"] == "upcoming"


def test_year_filter_keeps_visited_dots(app):
    """Visited cities always show; with a filter, a trip in another year doesn't count."""
    visit(app, "Denver")
    trip(app, [("Denver", "CO")], start=f"{NEXT_YEAR}-04-02", end=f"{NEXT_YEAR}-04-05")
    assert dots(app, year=THIS_YEAR)["Denver, CO"]["kind"] == "visited"
    assert dots(app, year=NEXT_YEAR)["Denver, CO"]["kind"] == "upcoming"


# --- The dots on the map page ---------------------------------------------------------

def test_map_draws_a_dot_per_city_with_its_kind(app, client):
    visit(app, "Denver")
    trip(app, [("Santa Fe", "NM")])
    page = map_page(client)
    assert re.search(r'<circle class="city-dot visited" data-city="Denver, CO"', page)
    assert re.search(r'<circle class="city-dot upcoming" data-city="Santa Fe, NM"', page)
    assert page.count('class="city-dot') == 2


def test_dot_sits_at_the_city_and_links_to_its_state(app, client):
    visit(app, "Denver")
    denver = find_city("Denver", "CO")
    page = map_page(client)
    # [^>]* allows the link's other attributes (class, data-details, ...).
    dot = re.search(r'<a href="/states/CO"[^>]*>\s*<circle class="city-dot visited" data-city="Denver, CO" '
                    r'cx="([\d.]+)" cy="([\d.]+)"', page)
    assert dot and (float(dot.group(1)), float(dot.group(2))) == (denver.x, denver.y)


def test_hovering_a_dot_tells_you_about_it(app, client):
    visit(app, "Denver", visit_date="2024-07-04")
    visit(app, "Denver", visit_date="2025-03-01")
    trip(app, [("Denver", "CO")])
    page = unescape(map_page(client))
    assert (f"<title>Denver, CO · visited 2024-07-04, 2025-03-01 · "
            f"upcoming: Four Corners weekend ({days_from_now(7)})</title>") in page


def test_dots_are_drawn_on_top_of_the_states(app, client):
    """In an SVG, what comes later is drawn on top, so the dots come after every state."""
    visit(app, "Denver")
    page = map_page(client)
    assert page.index('class="city-dot') > page.rindex('class="state ')


def test_year_filter_on_the_map_page_hides_other_years_trip_dots(app, client):
    trip(app, [("Santa Fe", "NM")], start=f"{NEXT_YEAR}-04-02", end=f"{NEXT_YEAR}-04-05")
    assert 'data-city="Santa Fe, NM"' not in map_page(client, f"/map?year={THIS_YEAR}")
    assert 'data-city="Santa Fe, NM"' in map_page(client, f"/map?year={NEXT_YEAR}")


def test_legend_explains_the_dots(client):
    page = map_page(client)
    assert "Visited city" in page
    assert "Upcoming city" in page


def test_dot_colors_exist_in_every_theme():
    """Light, chosen dark, and device dark all define the dot colors."""
    with open("tracker/static/style.css") as f:
        css = f.read()
    for name in ("--dot-visited:", "--dot-upcoming:", "--dot-ring:"):
        assert css.count(name) == 3, name


# --- Dot details on touch screens (phones and tablets can't hover) -------------------

def test_each_dot_link_carries_its_details_and_state_name(app, client):
    """map.js shows these in a box under the map when you tap a dot."""
    visit(app, "Denver", visit_date="2024-07-04")
    trip(app, [("Denver", "CO")])
    page = unescape(map_page(client))
    details = f"Denver, CO · visited 2024-07-04 · upcoming: Four Corners weekend ({days_from_now(7)})"
    assert f'<a href="/states/CO" class="dot-link" data-details="{details}" data-state-name="Colorado">' in page
    # The hover tooltip says the same thing.
    assert f"<title>{details}</title>" in page


def test_map_has_a_hidden_details_box_and_loads_map_js(client):
    page = map_page(client)
    assert '<div class="dot-details" id="dot-details" aria-live="polite" hidden>' in page
    assert 'src="/static/map.js"' in page


def test_map_explains_taps_on_touch_screens(client):
    """The hint is only shown on touch screens; style.css hides it elsewhere."""
    page = map_page(client)
    assert 'class="hint touch-dot-hint"' in page
    assert "Tap a dot once to see its visits and trips, and again to open its state." in page
    with open("tracker/static/style.css") as f:
        css = f.read()
    assert re.search(r"\.touch-dot-hint \{\s*display: none;", css)
    assert re.search(r"@media \(hover: none\) \{[^@]*\.touch-dot-hint \{\s*display: block;", css)


def test_map_script_handles_the_first_tap(client):
    script = client.get("/static/map.js").get_data(as_text=True)
    assert "(hover: none)" in script     # only on screens that can't hover
    assert "preventDefault" in script    # the first tap shows details instead of opening the state
    assert "dot-details" in script


# --- The legend's dot samples look like the dots ------------------------------------

def test_legend_dot_samples_have_a_thin_ring_like_the_dots():
    """A thin ring, so the sample keeps most of its color, like a dot on the map."""
    with open("tracker/static/style.css") as f:
        css = f.read()
    rule = re.search(r"\.city-swatch \{(.*?)\}", css, re.S).group(1)
    assert "border: 1px solid var(--dot-ring)" in rule
