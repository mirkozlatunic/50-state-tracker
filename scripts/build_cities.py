"""Build tracker/data/us_cities.csv: every US city with its position on our map.

This runs once by hand, not as part of the app:

    python scripts/build_cities.py 2023_Gaz_place_national.zip 2023_Gaz_counties_national.zip

The two files are the US Census "Gazetteer" files (public domain) from
https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html
They list every place and county with its latitude and longitude.

How a city gets its spot on the map:
1. A map "projection" flattens the globe onto paper. We use the Albers
   projection, the usual one for US maps (Alaska and Hawaii get their own).
2. Our map drawing is a projected map that's been moved and scaled. To find
   out exactly how, we line up known points: the middle of each mainland
   state (worked out from its counties), and for the Alaska and Hawaii insets,
   a few islands and Alaska's northernmost point.
3. Every city is then projected and moved the same way.
Coastal and border towns that land just outside their simplified outline are
moved just inside it. Finally, each state's capital must land inside its own
outline, or nothing is written.
"""
import csv
import io
import math
import sys
import zipfile
from pathlib import Path

# Let the script import the tracker package when run from the project folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tracker.map_data import MAP_HEIGHT, MAP_WIDTH  # noqa: E402
from tracker.map_shapes import (  # noqa: E402
    nearest_point_inside,
    point_in_state,
    polygon_area_and_center,
    state_polygons,
)
from tracker.states_data import STATES  # noqa: E402

STATE_CODES = {code for code, name in STATES}
OUTPUT = Path(__file__).resolve().parent.parent / "tracker" / "data" / "us_cities.csv"

# Albers projection settings: (center latitude, center longitude, two "standard parallels").
ALBERS = {
    "mainland": (37.5, -96.0, 29.5, 45.5),
    "AK": (50.0, -154.0, 55.0, 65.0),
    "HI": (13.0, -157.0, 8.0, 18.0),
}

# Reference points for the insets: (latitude, longitude) of a few islands and places.
# Hawaii's islands, from biggest to smallest, matched to the 8 pieces of the HI outline.
HAWAII_ISLANDS = [
    (19.59, -155.43),  # Hawaii (the Big Island)
    (20.80, -156.33),  # Maui
    (21.47, -157.98),  # Oahu
    (22.06, -159.53),  # Kauai
    (21.13, -157.02),  # Molokai
    (20.83, -156.92),  # Lanai
    (21.90, -160.16),  # Niihau
    (20.55, -156.60),  # Kahoolawe
]

# Words the Census adds after a name, e.g. "Denver city" or "Urban Honolulu CDP".
GOVERNMENT_ENDINGS = [
    " metropolitan government", " metro government", " consolidated government",
    " unified government", " urban county", " city and borough",
]
TYPE_ENDINGS = [" CDP", " city", " town", " village", " borough", " municipality", " township"]

# Extra names people actually use, for places whose official name is longer.
ALIASES = {
    ("HI", "Urban Honolulu"): "Honolulu",
    ("TN", "Nashville-Davidson"): "Nashville",
    ("KY", "Louisville/Jefferson County"): "Louisville",
    ("KY", "Lexington-Fayette"): "Lexington",
    ("ID", "Boise City"): "Boise",
    ("GA", "Augusta-Richmond County"): "Augusta",
    ("GA", "Athens-Clarke County"): "Athens",
    ("GA", "Macon-Bibb County"): "Macon",
    ("MT", "Butte-Silver Bow"): "Butte",
}

# Each state's capital: the safety check at the end.
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


def read_gazetteer(path):
    """Read a Census Gazetteer file (.txt, or the .zip it comes in) as a list of dictionaries."""
    path = Path(path)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            text = archive.read(archive.namelist()[0]).decode("utf-8")
    else:
        text = path.read_text(encoding="utf-8")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    # The last column name has trailing spaces in the Census files; strip every key and value.
    return [{key.strip(): value.strip() for key, value in row.items()} for row in reader]


def clean_name(name):
    """"Denver city" -> "Denver", "Indianapolis city (balance)" -> "Indianapolis"."""
    name = name.removesuffix(" (balance)")
    for ending in GOVERNMENT_ENDINGS + TYPE_ENDINGS:
        if name.endswith(ending):
            return name[: -len(ending)]
    return name


def albers(lat, lon, settings):
    """Project a latitude/longitude onto flat paper (spherical Albers equal-area conic).

    Returns (x, y) with x growing east and y growing north, in Earth radii.
    """
    lat0, lon0, parallel1, parallel2 = (math.radians(v) for v in settings)
    lat, lon = math.radians(lat), math.radians(lon)
    n = (math.sin(parallel1) + math.sin(parallel2)) / 2
    c = math.cos(parallel1) ** 2 + 2 * n * math.sin(parallel1)
    rho = math.sqrt(c - 2 * n * math.sin(lat)) / n
    rho0 = math.sqrt(c - 2 * n * math.sin(lat0)) / n
    theta = n * (lon - lon0)
    return rho * math.sin(theta), rho0 - rho * math.cos(theta)


def solve(matrix, vector):
    """Solve a small system of linear equations (Gaussian elimination)."""
    size = len(vector)
    rows = [list(matrix[i]) + [vector[i]] for i in range(size)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda r: abs(rows[r][col]))
        rows[col], rows[pivot] = rows[pivot], rows[col]
        for r in range(size):
            if r != col:
                factor = rows[r][col] / rows[col][col]
                rows[r] = [a - factor * b for a, b in zip(rows[r], rows[col])]
    return [rows[i][size] / rows[i][i] for i in range(size)]


def fit_affine(source, target):
    """Best-fit "affine" move (scale, turn, stretch, shift) from source points to target points.

    Least squares: picks the move that makes the total squared distance as small as possible.
    Returns a function that moves one (x, y) point.
    """
    sums = [[0.0] * 3 for _ in range(3)]
    rhs_x, rhs_y = [0.0] * 3, [0.0] * 3
    for (sx, sy), (tx, ty) in zip(source, target):
        row = (sx, sy, 1.0)
        for i in range(3):
            for j in range(3):
                sums[i][j] += row[i] * row[j]
            rhs_x[i] += row[i] * tx
            rhs_y[i] += row[i] * ty
    ax, ay = solve(sums, rhs_x), solve(sums, rhs_y)
    return lambda x, y: (ax[0] * x + ax[1] * y + ax[2], ay[0] * x + ay[1] * y + ay[2])


def fit_similarity(source, target):
    """Best-fit move that only scales, turns and shifts (no stretching), for the small insets.

    Uses complex numbers: a point (x, y) is x + yj, and the move is  a * point + b.
    """
    src = [complex(x, y) for x, y in source]
    dst = [complex(x, y) for x, y in target]
    src_mean, dst_mean = sum(src) / len(src), sum(dst) / len(dst)
    top = sum((d - dst_mean) * (s - src_mean).conjugate() for s, d in zip(src, dst))
    bottom = sum(abs(s - src_mean) ** 2 for s in src)
    a = top / bottom
    b = dst_mean - a * src_mean

    def move(x, y):
        point = a * complex(x, y) + b
        return point.real, point.imag
    return move


def flip(point):
    """Projections grow y northwards, the map grows y downwards: flip y."""
    return point[0], -point[1]


def state_centers_from_counties(counties):
    """The middle of each state on paper: the land-area-weighted average of its counties' centers."""
    totals = {}
    for county in counties:
        code = county["USPS"]
        if code not in STATE_CODES or code in ("AK", "HI"):
            continue
        weight = float(county["ALAND"])
        x, y = flip(albers(float(county["INTPTLAT"]), float(county["INTPTLONG"]), ALBERS["mainland"]))
        sx, sy, sw = totals.get(code, (0.0, 0.0, 0.0))
        totals[code] = (sx + x * weight, sy + y * weight, sw + weight)
    return {code: (sx / sw, sy / sw) for code, (sx, sy, sw) in totals.items()}


def map_center(code):
    """The middle of a state's outline on our map: area-weighted over all its pieces."""
    total_area = cx = cy = 0.0
    for polygon in state_polygons(code):
        area, (x, y) = polygon_area_and_center(polygon)
        total_area += area
        cx += x * area
        cy += y * area
    return cx / total_area, cy / total_area


def build_transforms(counties):
    """Work out how projected points line up with our map, for the mainland, Alaska and Hawaii."""
    # Mainland: match each state's middle on paper to its middle on the map.
    centers = state_centers_from_counties(counties)
    codes = sorted(centers)
    mainland = fit_affine([centers[c] for c in codes], [map_center(c) for c in codes])
    errors = [math.dist(mainland(*centers[c]), map_center(c)) for c in codes]
    print(f"mainland: {len(codes)} states lined up, average error {sum(errors) / len(errors):.1f}px, "
          f"worst {max(errors):.1f}px")

    # Hawaii: the 8 islands, biggest first, on paper and on the map.
    pieces = sorted((polygon_area_and_center(p) for p in state_polygons("HI")), reverse=True)
    hawaii = fit_similarity(
        [flip(albers(lat, lon, ALBERS["HI"])) for lat, lon in HAWAII_ISLANDS],
        [center for area, center in pieces[: len(HAWAII_ISLANDS)]],
    )

    # Alaska: the mainland's northernmost point (Utqiagvik/Barrow) and three big islands.
    ak_pieces = sorted(((polygon_area_and_center(p), p) for p in state_polygons("AK")),
                       key=lambda item: item[0][0], reverse=True)
    mainland_ak = ak_pieces[0][1]
    north_tip = min(mainland_ak, key=lambda point: point[1])
    island_centers = [center for (area, center), polygon in ak_pieces[1:]]

    def nearest_piece(x, y):
        """The center of the island piece closest to roughly where we expect it on the map."""
        return min(island_centers, key=lambda center: math.dist(center, (x, y)))

    alaska_refs = [
        ((71.39, -156.48), north_tip),                 # Utqiagvik (Barrow), the northern tip
        ((57.45, -153.40), nearest_piece(100, 560)),   # Kodiak Island
        ((63.40, -170.30), nearest_piece(45, 485)),    # St. Lawrence Island
        ((60.05, -166.35), nearest_piece(48, 519)),    # Nunivak Island
    ]
    alaska = fit_similarity(
        [flip(albers(lat, lon, ALBERS["AK"])) for (lat, lon), _ in alaska_refs],
        [target for _, target in alaska_refs],
    )
    return mainland, alaska, hawaii


def place_on_map(lat, lon, code, transforms):
    """A city's (x, y) position on our map."""
    mainland, alaska, hawaii = transforms
    if code == "AK":
        # The far end of the Aleutian Islands crosses the 180° line; keep the
        # longitudes continuous so they stay at the western edge.
        if lon > 0:
            lon -= 360
        return alaska(*flip(albers(lat, lon, ALBERS["AK"])))
    if code == "HI":
        return hawaii(*flip(albers(lat, lon, ALBERS["HI"])))
    return mainland(*flip(albers(lat, lon, ALBERS["mainland"])))


def build_rows(places, transforms):
    """One row per (state, name): cleaned names, aliases added, positions kept inside the map."""
    best = {}
    for place in places:
        code = place["USPS"]
        if code not in STATE_CODES:
            continue  # leaves out DC and Puerto Rico
        name = clean_name(place["NAME"])
        x, y = place_on_map(float(place["INTPTLAT"]), float(place["INTPTLONG"]), code, transforms)
        # A few far-off islands fall just outside the drawing: keep them at its edge.
        x = min(max(x, 0.0), MAP_WIDTH)
        y = min(max(y, 0.0), MAP_HEIGHT)
        # The outlines are simplified, so coastal and border towns can land just
        # outside their state (San Francisco in the ocean). Move them just inside.
        # (It also rounds to 0.1 pixel, as saved, and checks the rounded point.)
        x, y = nearest_point_inside(x, y, code)
        land = int(place["ALAND"])
        names = [name] + ([ALIASES[(code, name)]] if (code, name) in ALIASES else [])
        for each in names:
            key = (code, each.lower())
            # Two places with the same name in one state: keep the bigger one.
            if key not in best or land > best[key][0]:
                best[key] = (land, code, each, x, y)
    return sorted((row[1:] for row in best.values()), key=lambda r: (r[0], r[1].lower()))


def check_capitals(rows):
    """Every capital must land inside its own state. Returns the ones that don't."""
    position = {(code, name.lower()): (x, y) for code, name, x, y in rows}
    failures = []
    for code, capital in sorted(CAPITALS.items()):
        point = position.get((code, capital.lower()))
        if point is None or not point_in_state(*point, code):
            failures.append(f"{capital}, {code} at {point}")
    return failures


def main():
    """Read the two Census files, place every city, check the capitals and write the CSV."""
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    places = read_gazetteer(sys.argv[1])
    counties = read_gazetteer(sys.argv[2])
    transforms = build_transforms(counties)
    rows = build_rows(places, transforms)
    failures = check_capitals(rows)
    if failures:
        sys.exit("Not written. Capitals outside their state:\n  " + "\n  ".join(failures))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["state", "name", "x", "y"])
        writer.writerows(rows)
    print(f"All 50 capitals inside their state. Wrote {len(rows)} cities to {OUTPUT}")


if __name__ == "__main__":
    main()
