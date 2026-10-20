"""Opening, closing and setting up the SQLite database."""
import sqlite3

import click
from flask import current_app, g
from flask.cli import with_appcontext

from tracker.states_data import STATES


def get_db():
    """Return the database connection for the current request.

    `g` is a Flask object that lives for one request. We keep the connection
    on it, so all code in the same request shares one connection.
    """
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        # sqlite3.Row lets us read columns by name: row["code"] instead of row[1].
        g.db.row_factory = sqlite3.Row
        # SQLite only checks REFERENCES (foreign keys) when this is switched on.
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(error=None):
    """Close the connection at the end of the request, if one was opened."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the tables and add the 50 states.

    Safe to run more than once: existing tables are kept, and
    INSERT OR IGNORE skips states that are already there.
    """
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf8"))
    add_missing_columns(db)
    db.executemany("INSERT OR IGNORE INTO states (code, name) VALUES (?, ?)", STATES)
    db.commit()


def add_missing_columns(db):
    """Bring a database made by an older version of the app up to date (a "migration").

    "CREATE TABLE IF NOT EXISTS" skips tables that already exist, so a new
    column has to be added separately. PRAGMA table_info lists a table's columns.
    """
    visit_columns = {row["name"] for row in db.execute("PRAGMA table_info(visits)")}
    if "city" not in visit_columns:
        db.execute("ALTER TABLE visits ADD COLUMN city TEXT")


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Terminal command: `flask init-db`.

    `click` is the library Flask uses for terminal commands; it comes with Flask.
    @with_appcontext opens an app context first, so get_db() knows which app to use.
    """
    init_db()
    click.echo("Initialized the database.")


def init_app(app):
    """Connect the database helpers to the app."""
    # Run close_db automatically after every request.
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
