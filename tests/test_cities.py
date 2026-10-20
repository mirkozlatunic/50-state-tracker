"""Slice 12: the list of US cities and where each one sits on the map."""
import pytest

from tracker.cities import all_cities, cities_in_state, find_city
from tracker.map_data import MAP_HEIGHT, MAP_WIDTH
from tracker.map_shapes import point_in_state
from tests.test_states import EXPECTED_STATES

# Every state's capital, written out here as an independent check:
# each one must land inside its own state's outline on the map.
CAPITALS = {
    "AL": "Montgomery", "AK": "Juneau", "AZ": "Phoenix", "AR": "Little Rock",
    "CA": "Sacramento", "CO": "Denver", "CT": "Hartford", "DE": "Dover",
    "FL": "Tallahassee", "GA": "Atlanta", "HI": "Honolulu", "ID": "Boise",
    "IL": "Springfield", "IN": "Indianapolis", "IA": "Des Moines", "KS": "Topeka",
    "KY": "Frankfort", "LA": "Baton Rouge", "ME": "Augusta", "MD": "Annapolis",
    "MA": "Boston", "MI": "Lansing", "MN": "St. Paul", "MS": "Jackson",
    "MO": "Jefferson City", "MT": "Helena", "NE": "Lincoln", "NV": "Carson City",
    "NH": "Concord", "NJ": "Trenton", "NM": "Santa Fe", "NY": "Albany",
    "NC": "Raleigh", "ND": "Bismarck", "OH": "Columbus", "OK": "Oklahoma City",
    "OR": "Salem", "PA": "Harrisburg", "RI": "Providence", "SC": "Columbia",
    "SD": "Pierre", "TN": "Nashville", "TX": "Austin", "UT": "Salt Lake City",
    "VT": "Montpelier", "VA": "Richmond", "WA": "Olympia", "WV": "Charleston",
    "WI": "Madison", "WY": "Cheyenne",
}


# --- The list itself ----------------------------------------------------------------

def test_the_list_has_tens_of_thousands_of_places():
    """The Census lists about 32,000 places; we keep the ones in the 50 states."""
    assert len(all_cities()) > 25000


def test_only_the_50_states_are_included():
    """No Washington, D.C. and no Puerto Rico."""
    assert {city.state for city in all_cities()} == set(EXPECTED_STATES)


def test_names_are_cleaned_up():
    """"Denver city" becomes "Denver", "Urban Honolulu CDP" becomes "Urban Honolulu"."""
    endings = (" CDP", " city", " town", " village", " borough", "(balance)")
    leftovers = [city.name for city in all_cities() if city.name.endswith(endings)]
    assert leftovers == []


def test_each_name_appears_once_per_state():
    seen = [(city.state, city.name.lower()) for city in all_cities()]
    assert len(seen) == len(set(seen))


def test_every_city_is_somewhere_on_the_map():
    for city in all_cities():
        assert 0 <= city.x <= MAP_WIDTH and 0 <= city.y <= MAP_HEIGHT, city


# --- Finding a city ---------------------------------------------------------------

def test_find_a_city_by_name_and_state():
    city = find_city("Denver", "CO")
    assert (city.name, city.state) == ("Denver", "CO")


def test_finding_ignores_upper_and_lower_case_and_extra_spaces():
    assert find_city("  denver ", "co").name == "Denver"


@pytest.mark.parametrize("name, state", [
    ("Honolulu", "HI"),      # officially "Urban Honolulu"
    ("Nashville", "TN"),     # officially "Nashville-Davidson"
    ("Louisville", "KY"),    # officially "Louisville/Jefferson County"
    ("Boise", "ID"),         # officially "Boise City"
    ("Anchorage", "AK"),
    ("Indianapolis", "IN"),
])
def test_well_known_short_names_work(name, state):
    assert find_city(name, state) is not None


def test_unknown_city_gives_none():
    assert find_city("Denvr", "CO") is None
    assert find_city("Honolulu", "CO") is None  # real city, wrong state


def test_cities_in_a_state_are_sorted_and_only_from_that_state():
    names = [city.name for city in cities_in_state("CO")]
    assert "Denver" in names
    assert names == sorted(names, key=str.lower)
    assert {city.state for city in cities_in_state("CO")} == {"CO"}


# --- Where the cities land on the map ---------------------------------------------

@pytest.mark.parametrize("state, capital", sorted(CAPITALS.items()))
def test_every_capital_lands_inside_its_own_state(state, capital):
    city = find_city(capital, state)
    assert city is not None, capital
    assert point_in_state(city.x, city.y, state), f"{capital}, {state} at ({city.x}, {city.y})"


@pytest.mark.parametrize("name, state", [("Anchorage", "AK"), ("Fairbanks", "AK"), ("Hilo", "HI")])
def test_more_alaska_and_hawaii_cities_land_inside(name, state):
    """Alaska and Hawaii are small insets on the map, so check a few extra cities there."""
    city = find_city(name, state)
    assert point_in_state(city.x, city.y, state)


def test_cities_are_in_the_right_order_west_to_east_and_north_to_south():
    """On the map x grows to the right (east) and y grows downwards (south)."""
    seattle, denver, chicago, new_york = (
        find_city("Seattle", "WA"), find_city("Denver", "CO"),
        find_city("Chicago", "IL"), find_city("New York", "NY"),
    )
    assert seattle.x < denver.x < chicago.x < new_york.x
    miami, atlanta = find_city("Miami", "FL"), find_city("Atlanta", "GA")
    assert chicago.y < atlanta.y < miami.y


def test_a_city_is_not_inside_a_neighbouring_state():
    denver = find_city("Denver", "CO")
    assert not point_in_state(denver.x, denver.y, "KS")
    assert not point_in_state(denver.x, denver.y, "UT")


def test_the_corner_of_the_map_is_in_no_state():
    assert not any(point_in_state(1, 1, code) for code in EXPECTED_STATES)


def test_every_city_lands_inside_its_own_state():
    """The map's outlines are simplified, so a coastal city (San Francisco, Miami)
    can fall just outside its coast. The builder moves those dots just inside."""
    outside = [f"{city.name}, {city.state}" for city in all_cities()
               if not point_in_state(city.x, city.y, city.state)]
    assert outside == []
