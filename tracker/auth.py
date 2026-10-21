"""The login: one password for the whole app, form protection, and `flask set-password`.

How it works:
- You log in once. Flask then keeps a signed "session" cookie in your browser
  that says you're logged in, for 30 days. Every page checks that cookie.
- The password itself is never stored, only a "hash": a scrambled version
  that can be checked against but not turned back into the password.
- Every form carries a hidden one-time code (a "CSRF token"). Another website
  can't know it, so it can't make your browser submit forms here.
"""
import hmac
import secrets
import time
from pathlib import Path

import click
from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask.cli import with_appcontext
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint("auth", __name__)

# Pages that work without logging in: the login page itself, and what the
# home screen icon and the browser need (styles, icons, manifest).
PUBLIC_ENDPOINTS = {"auth.login", "static", "main.web_app_manifest", "main.favicon"}

# After this many wrong passwords within LOCK_SECONDS, logins pause.
MAX_WRONG_PASSWORDS = 5
LOCK_SECONDS = 60


def current_time():
    """The clock the login uses, in seconds. Tests replace it to "move time forward"."""
    return time.time()


def is_set_up():
    """True once a password and a secret key are saved (see `flask set-password`)."""
    return bool(current_app.config.get("SECRET_KEY") and current_app.config.get("PASSWORD_HASH"))


def is_logged_in():
    """True if this browser's session cookie says it logged in."""
    return bool(session.get("logged_in"))


def csrf_token():
    """This browser's hidden form code, made the first time it's needed."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def csrf_field():
    """The hidden form field, for templates: {{ csrf_field() }} inside every <form>.

    Markup tells the template this is finished HTML, so it isn't escaped.
    """
    return Markup(f'<input type="hidden" name="csrf_token" value="{csrf_token()}">')


@bp.before_app_request
def protect_every_page():
    """Runs before every request, on every page of the app.

    1. No password set yet: explain how to set one (the app never runs open).
    2. Not logged in: go to the login page, then back here afterwards.
    3. A submitted form without the right hidden code: refuse it (400).
    """
    if request.endpoint in ("static", "main.web_app_manifest", "main.favicon"):
        return None
    if not is_set_up():
        return render_template("setup.html"), 503

    if request.endpoint not in PUBLIC_ENDPOINTS and not is_logged_in():
        # full_path is the address including ?year=... ; strip a lone "?".
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))

    if request.method == "POST" and current_app.config["CSRF_ENABLED"]:
        expected = session.get("csrf_token", "")
        sent = request.form.get("csrf_token", "")
        # compare_digest compares in constant time, so timing gives no hints.
        if not expected or not hmac.compare_digest(expected, sent):
            abort(400)
    return None


def safe_next(target):
    """Where to go after logging in: only a page of this app, otherwise the map.

    "/years" is fine; "https://example.com" and "//example.com" (another
    website) are not.
    """
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return url_for("main.us_map")


def recent_failures():
    """The times of wrong passwords in the last LOCK_SECONDS, kept on the app."""
    failures = current_app.extensions.setdefault("login_failures", [])
    cutoff = current_time() - LOCK_SECONDS
    failures[:] = [moment for moment in failures if moment > cutoff]
    return failures


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Show the login form (GET) or check the password (POST)."""
    next_url = request.args.get("next", "")
    error = None
    status = 200

    if request.method == "POST":
        failures = recent_failures()
        if len(failures) >= MAX_WRONG_PASSWORDS:
            error, status = "Too many wrong passwords. Try again in a minute.", 429
        elif check_password_hash(current_app.config["PASSWORD_HASH"], request.form.get("password", "")):
            failures.clear()
            # A fresh session on login, so an old hidden form code can't be reused.
            session.clear()
            session["logged_in"] = True
            # permanent = keep the cookie for PERMANENT_SESSION_LIFETIME (30 days),
            # even after the browser is closed.
            session.permanent = True
            return redirect(safe_next(next_url))
        else:
            failures.append(current_time())
            error, status = "That password isn't right.", 400

    return render_template("login.html", error=error, next_url=next_url), status


@bp.route("/logout", methods=["POST"])
def logout():
    """Log out: forget this browser's session. Only a submitted form can do this."""
    session.clear()
    return redirect(url_for("auth.login"))


@click.command("set-password")
@with_appcontext
def set_password_command():
    """Terminal command: `flask set-password`. Asks for a new password and saves its hash.

    It also saves a new random secret key (which logs every browser out).
    Both go in the config file (instance/config.py), which git ignores.
    Any other settings already in that file are kept.
    """
    password = click.prompt("New password", hide_input=True, confirmation_prompt=True)
    # pbkdf2:sha256 works on every Python (Werkzeug's default, scrypt, needs a
    # newer OpenSSL than macOS's built-in Python has).
    password_hash = generate_password_hash(password, method="pbkdf2:sha256")
    secret_key = secrets.token_hex(32)

    path = Path(current_app.config["CONFIG_FILE"])
    kept = []
    if path.exists():
        kept = [line for line in path.read_text().splitlines()
                if not line.startswith(("SECRET_KEY", "PASSWORD_HASH"))]
    lines = kept + [f'SECRET_KEY = "{secret_key}"', f'PASSWORD_HASH = "{password_hash}"']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    click.echo(f"Password saved in {path}. Restart the app to use it.")


def init_app(app):
    """Connect the login to the app: its pages, the terminal command, and csrf_field()."""
    app.register_blueprint(bp)
    app.cli.add_command(set_password_command)
    app.jinja_env.globals["csrf_field"] = csrf_field
