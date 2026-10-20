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
- Run all tests: `pytest`

## The data

- The 50 states use their real official names and two-letter codes
  (e.g. California, CA). Washington, D.C. is not included.
- A visit has: state, visit date, a short note.
- A planned trip has: a name, start date, end date, and one or more states
  (I often combine nearby states into one weekend).

## Hard rules

- There are exactly 50 states.
- A state can have several visits, but it counts only once in my progress.
- A visit date can't be in the future.
- A planned trip must start in the future, and its end date can't be before its start date.
- I can plan a trip to a state I've already visited.
- A state counts as "visited" when I've spent time there outside the airport.
  Layovers don't count.

## Scope

- Now: states list, add visits, progress counter ("12 of 50"), planned trips.
- Later, not now: a clickable US map, trip costs, logins, putting it online.

## How to check it works

- `pytest` passes with no failures.
- With an empty database the progress shows "0 of 50".
- After adding visits to 3 different states, it shows "3 of 50".

## Folder rules

- `instance/` holds the SQLite database file. Never commit it.
- Tests use their own temporary database, never my real one.

## How we work

- Plan first, then code. Wait for my OK before writing code.
- Build one slice at a time. Write the tests first and show them to me
  before writing the code.
- Commit after each working slice. Never commit `.venv`.
