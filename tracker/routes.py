"""The pages of the app.

A "blueprint" is a group of related routes. We define them here and plug the
group into the app inside create_app().
"""
from datetime import date, timedelta

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

from tracker.cities import cities_in_state, find_city

from tracker.models import (
    TOTAL_STATES,
    add_trip,
    add_visit,
    count_visited_states,
    delete_trip,
    get_city_dots,
    get_next_trip,
    get_regions,
    get_state,
    get_state_statuses,
    get_states,
    get_trip,
    get_trip_years,
    get_upcoming_trips,
    get_visits_for_state,
    get_year_plan,
    set_trip_dates,
    shift_to_year,
    update_trip,
)
from tracker.map_data import MAP_HEIGHT, MAP_WIDTH, STATE_PATHS
from tracker.validation import (
    STATE_CODES,
    STATE_NAMES,
    parse_date,
    validate_trip,
    validate_trip_cities,
    validate_visit,
)

bp = Blueprint("main", __name__)


@bp.app_context_processor
def inject_progress():
    """Give every page the numbers for the "N of 50" counter, and the saved theme.

    A "context processor" adds values to every template automatically, so
    base.html can show the counter without each page passing it in.

    The theme comes from a cookie (a small note the browser keeps and sends
    back with every request), saved by theme.js. Only "light" and "dark" are
    accepted; anything else means "no choice saved, follow the device".
    """
    saved_theme = request.cookies.get("theme")
    return {
        "visited_count": count_visited_states(),
        "total_states": TOTAL_STATES,
        "theme": saved_theme if saved_theme in ("light", "dark") else None,
    }


@bp.route("/")
def home():
    """Send visitors from / to the states page.

    url_for("main.states") looks up the URL of the states() function below,
    so the link keeps working even if we rename the URL later.
    """
    return redirect(url_for("main.states"))


@bp.route("/states")
def states():
    """Show all 50 states A to Z, with visited ones marked."""
    return render_template("states.html", states=get_states())


@bp.route("/map")
def us_map():
    """Show the clickable US map: green = visited, orange = in an upcoming trip.

    ?year=2027 in the address only counts trips that start in 2027.
    request.args.get(..., type=int) turns the text into a number, and gives
    None if it isn't one, so /map?year=banana just shows the normal map.
    """
    today = date.today()
    year = request.args.get("year", type=int)
    return render_template(
        "map.html",
        states=get_states(),
        statuses=get_state_statuses(today, year=year),
        city_dots=get_city_dots(today, year=year),
        state_names=STATE_NAMES,
        # For phones: region cards and the next trip instead of the map.
        regions=get_regions(today, year=year),
        next_trip=get_next_trip(today),
        paths=STATE_PATHS,
        width=MAP_WIDTH,
        height=MAP_HEIGHT,
        year=year,
        trip_years=get_trip_years(today),
    )


@bp.route("/states/<code>")
def state_detail(code):
    """Show one state and its visits, newest first.

    <code> in the route is a "URL variable": for /states/CA, Flask calls
    state_detail(code="CA").
    """
    state = get_state(code)
    if state is None:
        # abort(404) stops here and shows the "Not Found" page.
        abort(404)
    return render_template(
        "state_detail.html",
        state=state,
        visits=get_visits_for_state(state["id"]),
        trips=get_upcoming_trips(date.today(), state_id=state["id"]),
    )


@bp.route("/visits/new", methods=["GET", "POST"])
def new_visit():
    """Show the add-visit form (GET) or save the filled-in form (POST).

    GET is what the browser sends when you open a page; POST is what it sends
    when you submit a form. `request.form` holds the submitted fields.
    """
    today = date.today()
    # On GET, ?state=CA in the URL (request.args) picks that state in the dropdown.
    # Anything that isn't one of the 50 codes is ignored, so the placeholder shows.
    linked_state = request.args.get("state", "").upper()
    form = {"state": linked_state if linked_state in STATE_CODES else ""}
    errors = []

    if request.method == "POST":
        form = {
            "state": request.form.get("state", ""),
            "visit_date": request.form.get("visit_date", ""),
            "note": request.form.get("note", "").strip(),
            "city": request.form.get("city", "").strip(),
        }
        errors = validate_visit(form["state"], form["visit_date"], today, city=form["city"])
        if not errors:
            # Store the date in one standard format, "YYYY-MM-DD", and the
            # city with its official spelling ("denver" -> "Denver").
            visit_date = parse_date(form["visit_date"]).isoformat()
            city = find_city(form["city"], form["state"]).name if form["city"] else None
            add_visit(form["state"], visit_date, form["note"], city)
            return redirect(url_for("main.state_detail", code=form["state"]))

    # Show the form: empty on GET, or again with errors after a bad POST.
    # 400 ("Bad Request") tells the browser the submitted form had problems.
    status = 400 if errors else 200
    # The city suggestions start with the chosen state's cities (if a state is chosen).
    city_options = cities_in_state(form["state"]) if form["state"] in STATE_CODES else ()
    return render_template(
        "visit_form.html", states=get_states(), form=form, errors=errors, today=today,
        city_options=city_options,
    ), status


@bp.route("/cities/<code>")
def city_names(code):
    """The city names of one state as JSON, e.g. ["Arvada", "Aurora", ...].

    JSON is a text format for data that JavaScript can read directly; the
    forms' cities.js fetches this to suggest cities while you type.
    """
    code = code.upper()
    if code not in STATE_CODES:
        abort(404)
    return jsonify([city.name for city in cities_in_state(code)])


@bp.route("/trips")
def trips():
    """Show the planned trips that haven't ended yet, soonest first."""
    return render_template("trips.html", trips=get_upcoming_trips(date.today()))


def read_trip_form():
    """Collect the fields of a submitted trip form into a dictionary."""
    return {
        "name": request.form.get("name", "").strip(),
        "start_date": request.form.get("start_date", ""),
        "end_date": request.form.get("end_date", ""),
        # getlist() returns every ticked checkbox with this name, e.g. ["AZ", "UT"].
        "states": request.form.getlist("states"),
        # And every city row, e.g. ["Denver, CO", "", ""].
        "cities": request.form.getlist("cities"),
    }


def trip_city_fields(form):
    """The city rows and suggestions for the trip form.

    Shows what's filled in plus empty rows: at least 3 rows, and always one
    empty row to add another city. Suggestions are the cities of the ticked states.
    """
    rows = [value for value in form.get("cities", []) if value.strip()]
    rows += [""] * max(3 - len(rows), 1)
    options = [city for code in form.get("states", []) if code in STATE_CODES
               for city in cities_in_state(code)]
    return {"city_rows": rows, "trip_city_options": options}


def get_return_to(source):
    """Read the return_to field from `source` (request.args or request.form).

    Only "years" is allowed; anything else means "go to /trips". Accepting
    only known values means a link can't send you off to another website.
    """
    return "years" if source.get("return_to") == "years" else ""


def redirect_after_trip_change(return_to):
    """After saving or deleting a trip, go back to the page you came from."""
    if return_to == "years":
        return redirect(url_for("main.years"))
    return redirect(url_for("main.trips"))


@bp.route("/years")
def years():
    """Show one column per year with its trips, new states and running total."""
    return render_template("years.html", plan=get_year_plan(date.today()), error=None)


@bp.route("/trips/<int:trip_id>/move", methods=["POST"])
def move_trip(trip_id):
    """Move a trip to another year: same month and day, same length.

    The "Move to" menu on each card submits this form, and so does dropping a
    card on another year (years.js picks the year and submits the menu). If
    the move breaks a trip rule, the year page is shown again with the reason.
    """
    trip = get_trip(trip_id)
    if trip is None:
        abort(404)

    today = date.today()
    year = request.form.get("year", type=int)
    if year is None or not today.year <= year <= today.year + 100:
        error = "Please choose a year from this year on."
    elif year == int(trip["start_date"][:4]):
        # Already in that year: nothing to do.
        return redirect(url_for("main.years"))
    else:
        new_start, new_end = shift_to_year(trip["start_date"], trip["end_date"], year)
        # The same rules as planning a trip, so a move can't put it in the past.
        errors = validate_trip(
            trip["name"], new_start.isoformat(), new_end.isoformat(), trip["states"], today
        )
        if not errors:
            set_trip_dates(trip_id, new_start.isoformat(), new_end.isoformat())
            return redirect(url_for("main.years"))
        error = errors[0]

    return render_template("years.html", plan=get_year_plan(today), error=error), 400


@bp.route("/trips/new", methods=["GET", "POST"])
def new_trip():
    """Show the plan-a-trip form (GET) or save the filled-in form (POST).

    With ?year=2027 (from the year page), the start date picker is limited to
    that year and saving goes back to the year page. The form has no action=,
    so it posts to the same address, and ?year= is still there on POST.
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)
    form = {"states": [], "cities": []}
    errors = []
    return_to = get_return_to(request.args) or get_return_to(request.form)

    # A year from this year up to 9999 (the largest year Python dates allow).
    year = request.args.get("year", type=int)
    if year is not None and not today.year <= year <= 9999:
        year = None
    if year is not None:
        heading = f"Plan a trip in {year}"
        min_start = max(tomorrow, date(year, 1, 1))
        max_start = date(year, 12, 31)
        return_to = "years"
    else:
        heading = "Plan a trip"
        min_start = tomorrow
        max_start = None

    if request.method == "POST":
        form = read_trip_form()
        errors = validate_trip(
            form["name"], form["start_date"], form["end_date"], form["states"], today
        )
        city_errors, cities = validate_trip_cities(form["cities"], form["states"])
        errors += city_errors
        if not errors:
            # Store the dates in one standard format, "YYYY-MM-DD".
            start = parse_date(form["start_date"]).isoformat()
            end = parse_date(form["end_date"]).isoformat()
            add_trip(form["name"], start, end, form["states"], cities)
            return redirect_after_trip_change(return_to)

    # Show the form: empty on GET, or again with errors after a bad POST.
    status = 400 if errors else 200
    return render_template(
        "trip_form.html",
        heading=heading,
        button_label="Save trip",
        states=get_states(),
        form=form,
        errors=errors,
        # The date picker's limits: trips must start in the future (and in
        # the chosen year, if there is one).
        min_start=min_start,
        max_start=max_start,
        return_to=return_to,
        # ** passes each key of the dictionary as its own argument.
        **trip_city_fields(form),
    ), status


@bp.route("/trips/<int:trip_id>/edit", methods=["GET", "POST"])
def edit_trip(trip_id):
    """Show a trip's edit form (GET) or save the changes (POST).

    <int:trip_id> only matches whole numbers and hands them over as an int.
    """
    trip = get_trip(trip_id)
    if trip is None:
        abort(404)

    today = date.today()
    form = trip
    errors = []
    return_to = get_return_to(request.args) or get_return_to(request.form)

    if request.method == "POST":
        form = read_trip_form()
        errors = validate_trip(
            form["name"], form["start_date"], form["end_date"], form["states"], today,
            keep_start=trip["start_date"],
        )
        city_errors, cities = validate_trip_cities(form["cities"], form["states"])
        errors += city_errors
        if not errors:
            start = parse_date(form["start_date"]).isoformat()
            end = parse_date(form["end_date"]).isoformat()
            update_trip(trip_id, form["name"], start, end, form["states"], cities)
            return redirect_after_trip_change(return_to)

    status = 400 if errors else 200
    return render_template(
        "trip_form.html",
        heading="Edit trip",
        button_label="Save changes",
        states=get_states(),
        form=form,
        errors=errors,
        # Tomorrow, or the trip's own start date if that's earlier (a trip in
        # progress), so the date picker lets you keep it.
        min_start=min(today + timedelta(days=1), parse_date(trip["start_date"])),
        max_start=None,
        return_to=return_to,
        **trip_city_fields(form),
    ), status


@bp.route("/trips/<int:trip_id>/delete", methods=["POST"])
def remove_trip(trip_id):
    """Delete a trip. Only a submitted form (POST) can do this; just opening the address gives 405."""
    if get_trip(trip_id) is None:
        abort(404)
    delete_trip(trip_id)
    return redirect_after_trip_change(get_return_to(request.form))
