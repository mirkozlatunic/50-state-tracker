"""The tracker package: builds the Flask app.

A folder with an __init__.py file is a Python "package", so other code can
write `from tracker import create_app`.
"""
import os
from datetime import timedelta

from flask import Flask


def create_app(test_config=None, config_file=None):
    """Build and return the Flask app.

    This is the "app factory" pattern: instead of one global app, we make a new
    one each time this runs. Tests use that to get an app with their own
    settings (like a temporary database), without touching the real one.

    The private settings (the secret key and the password hash) live in
    instance/config.py, written by `flask set-password`. Tests pass their own
    settings instead, so they never read it. `config_file` reads another file
    on top, which tests use to check that a saved password survives a restart.
    """
    # instance_relative_config=True makes Flask treat the instance/ folder
    # as the place for local, private files such as the database.
    app = Flask(__name__, instance_relative_config=True)

    # Default settings: the real database lives in instance/tracker.sqlite.
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "tracker.sqlite"),
        CONFIG_FILE=os.path.join(app.instance_path, "config.py"),
        # The login cookie lasts 30 days, can't be read by JavaScript (HttpOnly,
        # Flask's default), and isn't sent along when another website links here.
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        SESSION_COOKIE_SAMESITE="Lax",
        # The hidden form codes; only tests switch this off.
        CSRF_ENABLED=True,
    )

    if test_config is None:
        # The real app: read instance/config.py if it exists.
        app.config.from_pyfile("config.py", silent=True)
    else:
        # Tests pass their own settings, which replace the defaults above.
        app.config.from_mapping(test_config)
    if config_file:
        app.config.from_pyfile(config_file)

    # Make sure the instance/ folder exists so the database file can be created.
    os.makedirs(app.instance_path, exist_ok=True)

    # Connect the database helpers, then make sure the tables and the 50
    # states exist. init_db() keeps existing data, so this is safe on every start.
    from tracker import db
    db.init_app(app)
    with app.app_context():
        db.init_db()

    # Plug in the pages defined in routes.py, and the login that guards them.
    from tracker import auth, routes
    app.register_blueprint(routes.bp)
    auth.init_app(app)

    return app
