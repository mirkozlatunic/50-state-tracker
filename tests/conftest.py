"""Shared test setup.

pytest automatically loads this file. A "fixture" is a function that prepares
something a test needs (like an app or a client). A test asks for one just by
naming it as a parameter.
"""
import pytest

from tracker import create_app
from tracker.db import init_db


@pytest.fixture
def app(tmp_path):
    """Build a fresh app that uses a temporary database file.

    `tmp_path` is a built-in pytest fixture: a new empty folder for each test,
    deleted afterwards. So tests never touch the real database in instance/.
    """
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite")})

    # Create the tables and the 50 states in the temporary database.
    # An "app context" tells Flask which app is active, so code like
    # get_db() knows which database to open.
    with app.app_context():
        init_db()

    yield app


@pytest.fixture
def client(app):
    """A fake browser that can send requests to the app without running a server."""
    return app.test_client()
