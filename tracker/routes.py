"""The pages of the app.

A "blueprint" is a group of related routes. We define them here and plug the
group into the app inside create_app().
"""
from flask import Blueprint, redirect, url_for

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    """Send visitors from / to the states page.

    url_for("main.states") looks up the URL of the states() function below,
    so the link keeps working even if we rename the URL later.
    """
    return redirect(url_for("main.states"))


@bp.route("/states")
def states():
    """Show the list of states. Just a placeholder until slice 1."""
    return "States list coming soon."
