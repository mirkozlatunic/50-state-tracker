# 50 States Vacation Tracker

A small Flask web app to track trips through all 50 US states: which states
I've visited, when, and which weekend trips are planned next.

Private learning project, built with Python, Flask and SQLite.

![Clickable US map: visited states green, planned states orange](docs/screenshots/map.png)

*Screenshots show made-up example data.*

## Features

- **Clickable map:** every state links to its page. Green = visited,
  orange = in an upcoming trip, grey = not yet. A year filter shows only one
  year's plans.
- **Year planner:** one column per year with its trips, the new states it adds,
  and "By the end of 2027: 14 of 50". Drag a trip to another year to move it
  (or use its "Move to" menu). Plan, edit and delete trips right there.
- **States list:** all 50 states A to Z, with visited ones marked in bold.
- **Progress counter:** "7 of 50" in the header of every page.
- **Add visits:** state, date and an optional note.
- **State pages:** each state's visits (newest first) and the planned trips that include it.
- **Planned trips:** a name, start and end date, and one or more states, so nearby
  states can be combined into one weekend. Trips can be edited and deleted.
  Trips that have ended are hidden.

Every page reads the same database, so a change made on one page shows up on
all the others.

![The year planner with trips in 2026, 2027 and 2028](docs/screenshots/years.png)

| States list | State page |
|---|---|
| ![All 50 states with visited ones in bold](docs/screenshots/states.png) | ![Colorado's page with a planned trip](docs/screenshots/state-detail.png) |

| Planned trips | Add a visit |
|---|---|
| ![Four upcoming trips with Edit and Delete](docs/screenshots/trips.png) | ![The add-visit form](docs/screenshots/add-visit.png) |

| Plan a trip |
|---|
| ![The plan-a-trip form with a checkbox per state](docs/screenshots/plan-trip.png) |

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
- Editing a trip may keep its current start date even if it has passed, so a
  trip in progress can still be renamed.
- A trip belongs to the year it starts in. Moving it to another year keeps its
  month, day and length (Feb 29 becomes Feb 28 in a year without one). A move
  that would put the trip in the past is refused.
- On the map, a state that's both visited and planned shows as visited.

## Getting started

You need Python 3.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask run
```

Then open http://127.0.0.1:5000. On a Mac, port 5000 is often taken by AirPlay
Receiver; use `flask run --port 5001` and open http://127.0.0.1:5001 instead.

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
  map_data.py           # the 50 state outlines for the map
  models.py             # reading and saving states, visits and trips
  validation.py         # the visit and trip rules
  routes.py             # the pages
  templates/            # HTML templates
  static/style.css
  static/years.js       # drag and drop on the year page
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

## Credits

The map outlines come from ["Blank US Map (states only).svg"](https://commons.wikimedia.org/wiki/File:Blank_US_Map_(states_only).svg)
by Heitordp on Wikimedia Commons, released under CC0 (public domain).

## Not yet

Trip costs, logins, and putting the app online.
