"""Shared test setup.

pytest automatically loads this file. A "fixture" is a function that prepares
something a test needs (like an app or a client). A test asks for one just by
naming it as a parameter.
"""
import pytest
from werkzeug.security import generate_password_hash

from tracker import create_app
from tracker.db import init_db

# The password every test app uses. Werkzeug comes with Flask.
TEST_PASSWORD = "test-password"
# Its hash, made once: hashing is slow on purpose (that's what makes guessing
# hard), and doing it for each of the ~400 test apps took over a minute.
# The same method as `flask set-password` (scrypt needs a newer OpenSSL).
TEST_PASSWORD_HASH = generate_password_hash(TEST_PASSWORD, method="pbkdf2:sha256")


def make_settings(tmp_path, **changes):
    """The settings for a test app: a temporary database, a test password and
    secret key, and a temporary config file, so tests never touch instance/.

    The form protection (CSRF) is off here so tests can post forms simply;
    tests/test_login.py switches it on to test it.
    """
    settings = {
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.sqlite"),
        "SECRET_KEY": "test-secret-key",
        "PASSWORD_HASH": TEST_PASSWORD_HASH,
        "CONFIG_FILE": str(tmp_path / "config.py"),
        "CSRF_ENABLED": False,
    }
    settings.update(changes)
    return settings


@pytest.fixture
def app(tmp_path):
    """Build a fresh app that uses a temporary database file.

    `tmp_path` is a built-in pytest fixture: a new empty folder for each test,
    deleted afterwards. So tests never touch the real database in instance/.
    """
    app = create_app(make_settings(tmp_path))

    # Create the tables and the 50 states in the temporary database.
    # An "app context" tells Flask which app is active, so code like
    # get_db() knows which database to open.
    with app.app_context():
        init_db()

    yield app


@pytest.fixture
def client(app):
    """A fake browser that can send requests to the app without running a server.

    It starts logged in, so tests about other pages don't need to log in first.
    session_transaction() lets a test change the browser's login cookie directly.
    """
    client = app.test_client()
    with client.session_transaction() as session:
        session["logged_in"] = True
    return client


@pytest.fixture
def guest(app):
    """A fake browser that is NOT logged in."""
    return app.test_client()
