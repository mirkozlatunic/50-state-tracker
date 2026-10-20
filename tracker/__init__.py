"""The tracker package: builds the Flask app.

A folder with an __init__.py file is a Python "package", so other code can
write `from tracker import create_app`.
"""
import os

from flask import Flask


def create_app(test_config=None):
    """Build and return the Flask app.

    This is the "app factory" pattern: instead of one global app, we make a new
    one each time this runs. Tests use that to get an app with their own
    settings (like a temporary database), without touching the real one.
    """
    # instance_relative_config=True makes Flask treat the instance/ folder
    # as the place for local, private files such as the database.
    app = Flask(__name__, instance_relative_config=True)

    # Default settings: the real database lives in instance/tracker.sqlite.
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "tracker.sqlite"),
    )

    # Tests pass their own settings, which replace the defaults above.
    if test_config is not None:
        app.config.from_mapping(test_config)

    # Make sure the instance/ folder exists so the database file can be created.
    os.makedirs(app.instance_path, exist_ok=True)

    # Plug in the pages defined in routes.py.
    from tracker import routes
    app.register_blueprint(routes.bp)

    return app
