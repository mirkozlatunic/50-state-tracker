"""The pages of the app.

A "blueprint" is a group of related routes. We define them here and plug the
group into the app inside create_app().
"""
from datetime import date

from flask import Blueprint, abort, redirect, render_template, request, url_for

from tracker.models import (
    TOTAL_STATES,
    add_visit,
    count_visited_states,
    get_state,
    get_states,
    get_visits_for_state,
)
from tracker.validation import STATE_CODES, parse_date, validate_visit

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
        "state_detail.html", state=state, visits=get_visits_for_state(state["id"])
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
