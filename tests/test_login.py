"""Slice 19: one password for the whole app, form protection, and backups."""
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape

import pytest

import tracker.auth
from tracker import create_app
from tracker.db import init_db
from tracker.models import add_trip, add_visit
from tests.conftest import TEST_PASSWORD, make_settings

PAGES = ["/states", "/states/CA", "/map", "/visits/new", "/trips", "/trips/new", "/years"]


def log_in(client, password=TEST_PASSWORD, next_url=None):
    """Helper: submit the login form."""
    url = "/login" + (f"?next={next_url}" if next_url else "")
    return client.post(url, data={"password": password})


def page_text(client, url):
    """Helper: fetch a page and return its text as the browser would show it."""
    return unescape(client.get(url).get_data(as_text=True))


# --- Logged out: everything asks for the password --------------------------------------

@pytest.mark.parametrize("url", PAGES + ["/visits/1/edit", "/trips/1/edit", "/backup"])
def test_when_logged_out_every_page_asks_for_the_password(guest, url):
    response = guest.get(url)
    assert response.status_code == 302
    assert "/login?next=" in response.headers["Location"]


def test_posting_a_form_while_logged_out_does_nothing(app, guest):
    response = guest.post("/visits/new", data={"state": "CO", "visit_date": "2024-07-04", "note": ""})
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    with app.app_context():
        from tracker.db import get_db
        assert get_db().execute("SELECT COUNT(*) FROM visits").fetchone()[0] == 0


@pytest.mark.parametrize("url", ["/static/style.css", "/manifest.webmanifest", "/favicon.ico",
                                 "/static/icons/icon-180.png", "/login"])
def test_icons_manifest_styles_and_login_work_without_logging_in(guest, url):
    """So the home screen icon and the login page itself still work."""
    assert guest.get(url).status_code == 200


def test_login_page_shows_no_data(app, guest):
    """Someone who isn't logged in shouldn't even see your "N of 50"."""
    with app.app_context():
        add_visit("CO", "2024-07-04", "", None)
    page = page_text(guest, "/login")
    assert '<input type="password" name="password"' in page
    assert "of 50" not in page
    assert 'class="site-nav"' not in page


# --- Logging in and out ----------------------------------------------------------------

def test_one_login_opens_the_whole_app(app, guest):
    """Log in once, then move around: no page asks for the password again."""
    with app.app_context():
        visit_id = add_visit("CO", "2024-07-04", "", "Denver")
        trip_id = add_trip("Weekend", (date.today() + timedelta(days=7)).isoformat(),
                           (date.today() + timedelta(days=9)).isoformat(), ["CO"])
    log_in(guest)
    for url in PAGES + [f"/visits/{visit_id}/edit", f"/trips/{trip_id}/edit", "/backup"]:
        assert guest.get(url).status_code == 200, url


def test_right_password_logs_you_in_and_sends_you_back(guest):
    response = log_in(guest, next_url="/years")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/years")
    assert guest.get("/years").status_code == 200


def test_login_without_next_goes_to_the_map(guest):
    assert log_in(guest).headers["Location"].endswith("/map")


def test_next_can_only_be_a_page_of_this_app(guest):
    """Otherwise a link could log you in and then send you to another website."""
    for bad in ("https://example.com", "//example.com", "javascript:alert(1)"):
        assert log_in(guest, next_url=bad).headers["Location"].endswith("/map")
        guest.post("/logout")


def test_wrong_password_is_refused(guest):
    response = log_in(guest, password="nope")
    assert response.status_code == 400
    assert "That password isn't right." in unescape(response.get_data(as_text=True))
    assert guest.get("/map").status_code == 302


def test_after_five_wrong_passwords_logins_pause_for_a_minute(guest, monkeypatch):
    """Slows down anyone trying to guess. tracker.auth.current_time is the clock
    the app uses; the test moves it forward instead of really waiting."""
    clock = [1000.0]
    monkeypatch.setattr(tracker.auth, "current_time", lambda: clock[0])
    for _ in range(5):
        log_in(guest, password="nope")
    response = log_in(guest)  # the right password, but too soon
    assert response.status_code == 429  # "Too Many Requests"
    assert "Too many wrong passwords. Try again in a minute." in unescape(response.get_data(as_text=True))
    clock[0] += 61
    assert log_in(guest).status_code == 302


def test_you_stay_logged_in_for_30_days(guest):
    cookie = log_in(guest).headers["Set-Cookie"]
    # parsedate_to_datetime reads a date written like "Fri, 20 Nov 2026 19:30:00 GMT".
    expires = parsedate_to_datetime(re.search(r"Expires=([^;]+)", cookie).group(1))
    days_left = (expires - datetime.now(timezone.utc)).days
    assert 29 <= days_left <= 30
    assert "HttpOnly" in cookie  # JavaScript can't read it


def test_cookie_is_https_only_when_set_up_for_the_server(tmp_path):
    app = create_app(make_settings(tmp_path, SESSION_COOKIE_SECURE=True))
    with app.app_context():
        init_db()
    cookie = log_in(app.test_client()).headers["Set-Cookie"]
    assert "Secure" in cookie


def test_logging_out(client):
    response = client.post("/logout")
    assert response.headers["Location"].endswith("/login")
    assert client.get("/map").status_code == 302


def test_logged_in_pages_have_log_out_and_backup_links(client):
    page = client.get("/map").get_data(as_text=True)
    assert 'action="/logout"' in page
    assert 'href="/backup"' in page


# --- Setting the password ----------------------------------------------------------------

def test_set_password_saves_only_a_hash_and_a_secret_key(app, tmp_path):
    result = app.test_cli_runner().invoke(args=["set-password"], input="my secret\nmy secret\n")
    assert "Password saved" in result.output
    config = (tmp_path / "config.py").read_text()
    assert "my secret" not in config  # never the password itself
    assert re.search(r'PASSWORD_HASH = "(scrypt|pbkdf2)[^"]+"', config)
    assert re.search(r'SECRET_KEY = "[0-9a-f]{64}"', config)


def test_saved_password_works_after_a_restart(tmp_path):
    first = create_app(make_settings(tmp_path))
    first.test_cli_runner().invoke(args=["set-password"], input="new one\nnew one\n")
    # A "restart": a new app that reads the saved config file instead of test settings.
    settings = make_settings(tmp_path)
    del settings["PASSWORD_HASH"], settings["SECRET_KEY"]
    restarted = create_app(settings, config_file=str(tmp_path / "config.py"))
    with restarted.app_context():
        init_db()
    assert log_in(restarted.test_client(), password="new one").status_code == 302


def test_tests_never_read_the_real_config_file(app):
    """create_app() with test settings must not load instance/config.py."""
    assert app.config["SECRET_KEY"] == "test-secret-key"


def test_without_a_password_the_app_shows_how_to_set_one(tmp_path):
    """Never open without a password: it explains what to do instead."""
    settings = make_settings(tmp_path)
    del settings["PASSWORD_HASH"], settings["SECRET_KEY"]
    app = create_app(settings)
    with app.app_context():
        init_db()
    response = app.test_client().get("/map")
    assert response.status_code == 503  # "Service Unavailable"
    assert "flask set-password" in response.get_data(as_text=True)


# --- Form protection (CSRF) ------------------------------------------------------------

@pytest.fixture
def protected(tmp_path):
    """A logged-in browser on an app with the form protection switched on."""
    app = create_app(make_settings(tmp_path, CSRF_ENABLED=True))
    with app.app_context():
        init_db()
        add_visit("CO", "2024-07-04", "", "Denver")
        add_trip("Weekend", (date.today() + timedelta(days=7)).isoformat(),
                 (date.today() + timedelta(days=9)).isoformat(), ["CO"])
    client = app.test_client()
    with client.session_transaction() as session:
        session["logged_in"] = True
        session["csrf_token"] = "known-token"
    return client


@pytest.mark.parametrize("url", ["/visits/new", "/trips/new", "/visits/1/delete", "/trips/1/delete",
                                 "/visits/1/edit", "/trips/1/edit", "/trips/1/move", "/logout"])
def test_forms_without_the_hidden_code_are_refused(protected, url):
    response = protected.post(url, data={})
    assert response.status_code == 400
    assert protected.get("/trips").status_code == 200  # still logged in, nothing deleted
    assert "Weekend" in protected.get("/trips").get_data(as_text=True)


def test_forms_with_the_hidden_code_work(protected):
    response = protected.post("/visits/1/delete", data={"csrf_token": "known-token"})
    assert response.status_code == 302


def test_wrong_hidden_code_is_refused(protected):
    assert protected.post("/visits/1/delete", data={"csrf_token": "guess"}).status_code == 400


@pytest.mark.parametrize("url", ["/visits/new", "/trips/new", "/visits/1/edit", "/trips/1/edit",
                                 "/trips", "/years", "/states/CO", "/map"])
def test_every_form_on_every_page_has_the_hidden_code(protected, url):
    page = protected.get(url).get_data(as_text=True)
    forms = re.findall(r'<form method="post".*?</form>', page, re.S)
    assert forms, url
    for form in forms:
        assert '<input type="hidden" name="csrf_token" value="known-token">' in form


def test_login_form_has_the_hidden_code_too(tmp_path):
    app = create_app(make_settings(tmp_path, CSRF_ENABLED=True))
    page = app.test_client().get("/login").get_data(as_text=True)
    assert re.search(r'<input type="hidden" name="csrf_token" value="[^"]{20,}">', page)


# --- Backup -------------------------------------------------------------------------------

def test_backup_downloads_the_database(app, client, tmp_path):
    with app.app_context():
        add_visit("CO", "2024-07-04", "Red Rocks", "Denver")
    response = client.get("/backup")
    assert response.status_code == 200
    assert f'filename=tracker-{date.today().isoformat()}.sqlite' in response.headers["Content-Disposition"]
    assert response.data.startswith(b"SQLite format 3\x00")  # every SQLite file starts like this
    copy = tmp_path / "copy.sqlite"
    copy.write_bytes(response.data)
    notes = sqlite3.connect(copy).execute("SELECT note FROM visits").fetchall()
    assert notes == [("Red Rocks",)]
