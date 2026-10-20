"""Geometry for the map outlines: "is this point inside that state?".

The outlines in map_data.py are SVG paths made only of straight lines, so each
state is one or more polygons (lists of corner points). Used by the tests and
by scripts/build_cities.py, which places the cities on the map.
"""
import math
import re
from functools import lru_cache

from tracker.map_data import STATE_PATHS

# A command letter, or a number such as 15.8, -.3 or 2e-1.
TOKEN = re.compile(r"[MmLlHhVvZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def parse_path(d):
    """Turn an SVG path string into a list of polygons, each a list of (x, y) points.

    Only the commands the map uses are handled: M/m (move to), L/l (line to),
    H/h (horizontal line), V/v (vertical line) and Z/z (close the shape).
    Lower-case letters mean "relative to the current point".
    """
    tokens = TOKEN.findall(d)
    polygons = []
    current = []
    x = y = 0.0
    start_x = start_y = 0.0
    command = None
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            command = token
            i += 1
            if command in "Zz":
                if current:
                    polygons.append(current)
                current = []
                x, y = start_x, start_y
            continue

        if command in "Mm":
            dx, dy = float(tokens[i]), float(tokens[i + 1])
            i += 2
            x, y = (x + dx, y + dy) if command == "m" else (dx, dy)
            if current:
                polygons.append(current)
            current = [(x, y)]
            start_x, start_y = x, y
            # Numbers after the first pair of a move are lines, in the same style.
            command = "l" if command == "m" else "L"
        elif command in "Ll":
            dx, dy = float(tokens[i]), float(tokens[i + 1])
            i += 2
            x, y = (x + dx, y + dy) if command == "l" else (dx, dy)
            current.append((x, y))
        elif command in "Hh":
            value = float(tokens[i])
            i += 1
            x = x + value if command == "h" else value
            current.append((x, y))
        elif command in "Vv":
            value = float(tokens[i])
            i += 1
            y = y + value if command == "v" else value
            current.append((x, y))
        else:
            raise ValueError(f"Unsupported path command: {command}")

    if current:
        polygons.append(current)
    return polygons


@lru_cache(maxsize=None)
def state_polygons(code):
    """The polygons of one state's outline. lru_cache remembers the answer,
    so each outline is only worked out once."""
    return parse_path(STATE_PATHS[code])


def point_in_polygon(x, y, polygon):
    """Ray casting: draw a line from the point to the right and count how often
    it crosses the polygon's edges. An odd count means the point is inside."""
    inside = False
    count = len(polygon)
    for i in range(count):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % count]
        if (y1 > y) != (y2 > y):
            crossing_x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < crossing_x:
                inside = not inside
    return inside


def point_in_state(x, y, code):
    """True if the map point (x, y) is inside the outline of the state with this code."""
    return any(point_in_polygon(x, y, polygon) for polygon in state_polygons(code))


def polygon_area_and_center(polygon):
    """The area and the center of mass of one polygon (the "shoelace formula")."""
    area = cx = cy = 0.0
    count = len(polygon)
    for i in range(count):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % count]
        cross = x1 * y2 - x2 * y1
        area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    area /= 2
    if area == 0:
        return 0.0, polygon[0]
    return abs(area), (cx / (6 * area), cy / (6 * area))


def nearest_point_on_segment(px, py, ax, ay, bx, by):
    """The point on the line from (ax, ay) to (bx, by) that's closest to (px, py)."""
    dx, dy = bx - ax, by - ay
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return ax, ay
    # t is how far along the line (0 = start, 1 = end) the closest point is.
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_squared))
    return ax + t * dx, ay + t * dy


def nearest_point_inside(x, y, code, decimals=1):
    """Move a point that's just outside a state's outline to just inside it.

    Finds the closest spot on the outline, then steps a little further, into
    the state. Positions are rounded to `decimals` places (as they're saved),
    and the rounded point is what has to be inside. Returns the rounded point
    unchanged if it's already inside.
    """
    x, y = round(x, decimals), round(y, decimals)
    if point_in_state(x, y, code):
        return x, y

    # The closest spot on the outline, and the piece (polygon) it belongs to.
    best = None
    for polygon in state_polygons(code):
        for i in range(len(polygon)):
            ax, ay = polygon[i]
            bx, by = polygon[(i + 1) % len(polygon)]
            nx, ny = nearest_point_on_segment(x, y, ax, ay, bx, by)
            distance = (nx - x) ** 2 + (ny - y) ** 2
            if best is None or distance < best[0]:
                best = (distance, nx, ny, polygon)
    distance, nx, ny, polygon = best

    # First try straight on (away from where the point was), then 16 other
    # directions, each with small to larger steps.
    length = max(distance ** 0.5, 1e-9)
    directions = [((nx - x) / length, (ny - y) / length)]
    directions += [(math.cos(a * math.pi / 8), math.sin(a * math.pi / 8)) for a in range(16)]
    for dx, dy in directions:
        for step in (0.2, 0.4, 0.6, 1.0, 1.5, 2.0, 3.0):
            cx, cy = round(nx + dx * step, decimals), round(ny + dy * step, decimals)
            if point_in_state(cx, cy, code):
                return cx, cy

    # Last resort for a sliver of an island: the middle of that piece.
    area, (cx, cy) = polygon_area_and_center(polygon)
    return round(cx, decimals), round(cy, decimals)
