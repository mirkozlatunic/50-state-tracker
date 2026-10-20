# 50 States Vacation Tracker

## Purpose

A small web app to track my trips through all 50 US states: which states I've
visited, when, and which weekend trips are planned next.
Private learning project. The data is my own real trip data.

## About me

I'm learning Python and Flask. Comment every function and explain new concepts
in 1–2 sentences when you use them. Prefer simple, readable code over clever code.

## Stack

Python 3, Flask, SQLite, pytest. No other packages without asking me first.

## Setup and commands

- Activate the virtual environment on my Mac: `source .venv/bin/activate`
- Run the app: `flask run`, then open http://127.0.0.1:5000
  (if port 5000 is taken by macOS AirPlay Receiver: `flask run --port 5001`)
- Run all tests: `pytest`

## The data

- The 50 states use their real official names and two-letter codes
  (e.g. California, CA). Washington, D.C. is not included.
- A visit has: state, visit date, a short note.
- A planned trip has: a name, start date, end date, and one or more states
  (I often combine nearby states into one weekend).
- Trips can be edited, deleted, or moved to another year.
- The map outlines in `tracker/map_data.py` come from a CC0 (public domain)
  Wikimedia Commons SVG; the source is noted at the top of that file.

## Hard rules

- There are exactly 50 states.
- A state can have several visits, but it counts only once in my progress.
- A visit date can't be in the future.
- A planned trip must start in the future, and its end date can't be before its start date.
- I can plan a trip to a state I've already visited.
- A state counts as "visited" when I've spent time there outside the airport.
  Layovers don't count.
- Editing a trip may keep its current start date even if that date has passed
  (so a trip in progress can be renamed). Any other start date must be in the future.
- A trip belongs to the year it starts in. Trips that have ended are hidden.
- Moving a trip to another year keeps its month, day and length
  (Feb 29 becomes Feb 28 in a year without one). The trip rules still apply.
- Map colors: green = visited, orange = in a trip that hasn't ended,
  grey = neither. Visited wins over planned.

## Scope

- Done: states list, add visits, progress counter ("12 of 50"), planned trips,
  editing and deleting trips, a clickable US map, and a year page where trips
  can be dragged between years.
- Later, not now: trip costs, logins, putting it online.

## How to check it works

- `pytest` passes with no failures.
- With an empty database the progress shows "0 of 50".
- After adding visits to 3 different states, it shows "3 of 50".
- On `/map`, a visited state is green and a state in an upcoming trip is orange.
- On `/years`, dragging a trip to another year changes its dates on `/trips` too.

## Folder rules

- `instance/` holds the SQLite database file. Never commit it.
- Tests use their own temporary database, never my real one.

## How we work

- Plan first, then code. Wait for my OK before writing code.
- Build one slice at a time. Write the tests first and show them to me
  before writing the code.
- Commit after each working slice. Never commit `.venv`.
