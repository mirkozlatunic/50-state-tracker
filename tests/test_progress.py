"""Slice 2: the "N of 50" progress counter."""


def add_visit(client, state, visit_date="2024-07-04"):
    """Helper: add one visit through the form, like you would in the browser."""
    client.post("/visits/new", data={"state": state, "visit_date": visit_date, "note": ""})


def progress_text(client):
    """Helper: the states page as text, to look for the counter in."""
    return client.get("/states").get_data(as_text=True)


def test_three_different_states_show_3_of_50(client):
    """From "How to check it works" in CLAUDE.md."""
    add_visit(client, "CA")
    add_visit(client, "NV")
    add_visit(client, "AZ")
    assert "3 of 50" in progress_text(client)


def test_several_visits_to_one_state_count_once(client):
    """Hard rule: a state can have several visits, but counts once."""
    add_visit(client, "CA", "2023-05-01")
    add_visit(client, "CA", "2024-07-04")
    add_visit(client, "CA", "2025-01-15")
    assert "1 of 50" in progress_text(client)


def test_rejected_visit_does_not_count(client):
    add_visit(client, "CA", "2999-01-01")  # in the future, so rejected
    assert "0 of 50" in progress_text(client)


def test_counter_shows_on_the_add_visit_page_too(client):
    """The counter is in the shared layout, so every page shows it."""
    add_visit(client, "CA")
    page = client.get("/visits/new").get_data(as_text=True)
    assert "1 of 50" in page


def test_visited_state_is_marked_on_the_states_page(client):
    add_visit(client, "CA")
    page = progress_text(client)
    # The California list item gets the "visited" class; Nevada doesn't.
    assert '<li class="visited">' in page
    assert page.count('<li class="visited">') == 1
