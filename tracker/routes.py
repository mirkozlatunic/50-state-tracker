"""The pages of the app.

A "blueprint" is a group of related routes. We define them here and plug the
group into the app inside create_app().
"""
from flask import Blueprint, redirect, render_template, url_for

from tracker.models import TOTAL_STATES, count_visited_states, get_states

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
