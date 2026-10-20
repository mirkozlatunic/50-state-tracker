# 50 States Vacation Tracker

A small Flask web app to track trips through all 50 US states: which states
I've visited, when, and which weekend trips are planned next.

Private learning project, built with Python, Flask and SQLite.

![States list with the progress counter](docs/screenshots/states.png)

*Screenshots show made-up example data.*

## Features

- **States list:** all 50 states A to Z, with visited ones marked in bold.
- **Progress counter:** "7 of 50" in the header of every page.
- **Add visits:** state, date and an optional note.
- **State pages:** each state's visits (newest first) and the planned trips that include it.
- **Planned trips:** a name, start and end date, and one or more states, so nearby
  states can be combined into one weekend. Trips that have ended are hidden.

| State page | Planned trips |
|---|---|
| ![California's page with two visits](docs/screenshots/state-detail.png) | ![Two upcoming trips](docs/screenshots/trips.png) |

| Add a visit | Plan a trip |
|---|---|
| ![The add-visit form](docs/screenshots/add-visit.png) | ![The plan-a-trip form with a checkbox per state](docs/screenshots/plan-trip.png) |

## Rules the app follows

- There are exactly 50 states, with their official names and two-letter codes.
  Washington, D.C. is not included.
- A state can have several visits, but counts only once in the progress.
- A visit date can't be in the future (today is fine).
- A planned trip must start in the future (tomorrow at the earliest), and its
  end date can't be before its start date. A one-day trip is fine.
- A trip can include states that were already visited. Planning a trip doesn't
  count as visiting.
- A state counts as visited only after spending time there outside the
  airport. Layovers don't count. The app can't check this, so the visit form
  reminds you.

## Getting started

You need Python 3.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask run
```

Then open http://127.0.0.1:5000.

The database is created automatically at `instance/tracker.sqlite` on the first
start. It's kept out of git. `flask init-db` sets it up by hand; running it
again keeps your data.

## Running the tests

```bash
pytest
```

Each test uses its own temporary database, never the real one in `instance/`.

## Project structure

```
app.py                  # lets plain `flask run` find the app
tracker/
  __init__.py           # create_app(): builds the app and sets up the database
  db.py                 # database connection, init_db(), `flask init-db`
  schema.sql            # the tables
  states_data.py        # the 50 states
  models.py             # reading and saving states, visits and trips
  validation.py         # the visit and trip rules
  routes.py             # the pages
  templates/            # HTML templates
  static/style.css
tests/                  # pytest tests, one file per feature
docs/screenshots/       # images for this README
```

## Database tables

| Table | Columns |
|---|---|
| `states` | `id`, `code` (e.g. CA), `name` (e.g. California) |
| `visits` | `id`, `state_id`, `visit_date`, `note` |
| `trips` | `id`, `name`, `start_date`, `end_date` |
| `trip_states` | `trip_id`, `state_id`. Links a trip to each of its states |

Dates are stored as `YYYY-MM-DD` text.

## Not yet

A clickable US map, trip costs, logins, and putting the app online.
