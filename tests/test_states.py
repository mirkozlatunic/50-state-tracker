"""Slice 1: the 50 states are in the database and listed on the states page."""
from tracker.db import get_db, init_db
from tracker.models import get_states

# The official names and two-letter codes of all 50 states.
# Written out here on purpose, so the test checks the app's data against an
# independent list instead of against itself.
EXPECTED_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}


def test_there_are_exactly_50_states(app):
    """Hard rule: exactly 50 states."""
    with app.app_context():
        assert len(get_states()) == 50


def test_states_have_official_names_and_codes(app):
    """Every state has its real name and two-letter code, nothing extra."""
    with app.app_context():
        actual = {state["code"]: state["name"] for state in get_states()}
    assert actual == EXPECTED_STATES


def test_washington_dc_is_not_a_state(app):
    """Washington, D.C. is not included."""
    with app.app_context():
        codes = [state["code"] for state in get_states()]
    assert "DC" not in codes


def test_states_are_sorted_by_name(app):
    """The list comes back A to Z, which is how the page shows it."""
    with app.app_context():
        names = [state["name"] for state in get_states()]
    assert names == sorted(names)


def test_running_init_db_twice_still_gives_50_states(app):
    """Setting up the database again must not create duplicate states."""
    with app.app_context():
        init_db()
        count = get_db().execute("SELECT COUNT(*) FROM states").fetchone()[0]
    assert count == 50


def test_init_db_command(app):
    """`flask init-db` sets up the database from the terminal.

    test_cli_runner() runs Flask terminal commands inside the test, without
    opening a real terminal.
    """
    result = app.test_cli_runner().invoke(args=["init-db"])
    assert "Initialized the database" in result.output


def test_states_page_lists_all_50_states(client):
    """Every state name appears on the states page."""
    page = client.get("/states").get_data(as_text=True)
    for name in EXPECTED_STATES.values():
        assert name in page


def test_empty_database_shows_0_of_50(client):
    """With no visits yet, the progress counter reads "0 of 50"."""
    page = client.get("/states").get_data(as_text=True)
    assert "0 of 50" in page
