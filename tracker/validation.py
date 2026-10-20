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


def validate_trip(name, start_date, end_date, state_codes, today):
    """Check a new planned trip. Returns a list of error messages; empty means OK.

    `state_codes` is a list like ["AZ", "UT"]. `today` is passed in, like in
    validate_visit(), so tests can pick the day.
    """
    errors = []

    if not name.strip():
        errors.append("Please enter a trip name.")

    start = None
    if not start_date:
        errors.append("Please enter a start date.")
    else:
        start = parse_date(start_date)
        if start is None:
            errors.append("Please enter a real start date.")
        elif start <= today:
            errors.append("A planned trip must start in the future.")

    end = None
    if not end_date:
        errors.append("Please enter an end date.")
    else:
        end = parse_date(end_date)
        if end is None:
            errors.append("Please enter a real end date.")

    # Only compare the dates when both are real dates.
    if start and end and end < start:
        errors.append("The end date can't be before the start date.")

    if not state_codes:
        errors.append("Please choose at least one state.")
    elif any(code not in STATE_CODES for code in state_codes):
        errors.append("Please choose only from the 50 states.")

    return errors
