"""The rules a visit (and later a trip) must follow.

These functions only check input and return error messages. They don't save
anything, which keeps them easy to test on their own.
"""
from datetime import datetime

from tracker.states_data import STATES

STATE_CODES = {code for code, name in STATES}


def parse_date(text):
    """Turn "YYYY-MM-DD" into a date object, or return None if it isn't a real date.

    strptime ("string parse time") reads text using a pattern; it raises a
    ValueError for things like February 30th, which we catch.
    """
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def validate_visit(state_code, visit_date, today):
    """Check a new visit. Returns a list of error messages; empty means OK.

    `today` is passed in instead of looked up here, so tests can pick the day.
    """
    errors = []

    if state_code not in STATE_CODES:
        errors.append("Please choose one of the 50 states.")

    if not visit_date:
        errors.append("Please enter a visit date.")
    else:
        parsed = parse_date(visit_date)
        if parsed is None:
            errors.append("Please enter a real date.")
        elif parsed > today:
            errors.append("The visit date can't be in the future.")

    return errors
