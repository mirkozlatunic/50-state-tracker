"""The pages of the app.

A "blueprint" is a group of related routes. We define them here and plug the
group into the app inside create_app().
"""
from datetime import date, timedelta

from flask import Blueprint, abort, redirect, render_template, request, url_for

from tracker.models import (
    TOTAL_STATES,
    add_trip,
    add_visit,
    count_visited_states,
    delete_trip,
    get_state,
    get_state_statuses,
    get_states,
    get_trip,
    get_trip_years,
    get_upcoming_trips,
    get_visits_for_state,
    get_year_plan,
    update_trip,
)
from tracker.map_data import MAP_HEIGHT, MAP_WIDTH, STATE_PATHS
from tracker.validation import STATE_CODES, parse_date, validate_trip, validate_visit

bp = Blueprint("main", __name__)


@bp.app_context_processor
def inject_progress():
    """Give every page the numbers for the "N of 50" counter.

    A "context processor" adds values to every template automatically, so
    base.html can show the counter without each page passing it in.
    """
    return {"visited_count": count_visited_states(), "total_states": TOTAL_STATES}


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
        }
        errors = validate_visit(form["state"], form["visit_date"], today)
        if not errors:
            # Store the date in one standard format, "YYYY-MM-DD".
            visit_date = parse_date(form["visit_date"]).isoformat()
            add_visit(form["state"], visit_date, form["note"])
            return redirect(url_for("main.state_detail", code=form["state"]))

    # Show the form: empty on GET, or again with errors after a bad POST.
    # 400 ("Bad Request") tells the browser the submitted form had problems.
    status = 400 if errors else 200
    return render_template(
        "visit_form.html", states=get_states(), form=form, errors=errors, today=today
    ), status


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
    }


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
    return render_template("years.html", plan=get_year_plan(date.today()))


@bp.route("/trips/new", methods=["GET", "POST"])
def new_trip():
    """Show the plan-a-trip form (GET) or save the filled-in form (POST).

    With ?year=2027 (from the year page), the start date picker is limited to
    that year and saving goes back to the year page. The form has no action=,
    so it posts to the same address, and ?year= is still there on POST.
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)
    form = {"states": []}
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
        if not errors:
            # Store the dates in one standard format, "YYYY-MM-DD".
            start = parse_date(form["start_date"]).isoformat()
            end = parse_date(form["end_date"]).isoformat()
            add_trip(form["name"], start, end, form["states"])
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
        if not errors:
            start = parse_date(form["start_date"]).isoformat()
            end = parse_date(form["end_date"]).isoformat()
            update_trip(trip_id, form["name"], start, end, form["states"])
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
    ), status


@bp.route("/trips/<int:trip_id>/delete", methods=["POST"])
def remove_trip(trip_id):
    """Delete a trip. Only a submitted form (POST) can do this; just opening the address gives 405."""
    if get_trip(trip_id) is None:
        abort(404)
    delete_trip(trip_id)
    return redirect_after_trip_change(get_return_to(request.form))
