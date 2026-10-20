"""The list of US cities and their positions on the map.

The list lives in tracker/data/us_cities.csv, built once by scripts/build_cities.py
from US Census data. It never changes while the app runs, so it's read once
into memory instead of being copied into the database.
"""
import csv
from collections import namedtuple
from functools import lru_cache
from pathlib import Path

CITIES_FILE = Path(__file__).parent / "data" / "us_cities.csv"

# A namedtuple is a small, read-only record: city.name, city.state, city.x, city.y.
City = namedtuple("City", ["state", "name", "x", "y"])


@lru_cache(maxsize=None)
def all_cities():
    """Every city, read from the CSV the first time it's needed.

    lru_cache remembers the result, so the file is only read once.
    """
    with open(CITIES_FILE, newline="", encoding="utf-8") as f:
        return tuple(
            City(row["state"], row["name"], float(row["x"]), float(row["y"]))
            for row in csv.DictReader(f)
        )


@lru_cache(maxsize=None)
def cities_by_key():
    """All cities in a dictionary keyed by (state, lower-case name), for quick lookups."""
    return {(city.state, city.name.lower()): city for city in all_cities()}


def find_city(name, state_code):
    """Return the City called `name` in that state, or None if there's no such city.

    Upper/lower case and extra spaces don't matter: " denver", "co" finds Denver, CO.
    """
    return cities_by_key().get((state_code.strip().upper(), name.strip().lower()))


@lru_cache(maxsize=None)
def cities_in_state(state_code):
    """All cities in one state, A to Z (ignoring upper/lower case)."""
    return tuple(sorted(
        (city for city in all_cities() if city.state == state_code),
        key=lambda city: city.name.lower(),
    ))
