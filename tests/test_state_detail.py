"""Slice 3: one page per state, showing its visits."""


def add_visit(client, state, visit_date, note=""):
    """Helper: add one visit through the form, like you would in the browser."""
    client.post("/visits/new", data={"state": state, "visit_date": visit_date, "note": note})


def page_text(client, url):
    """Helper: fetch a page and return its HTML as text."""
    return client.get(url).get_data(as_text=True)


def test_state_page_shows_name_and_code(client):
    page = page_text(client, "/states/CA")
    assert "California" in page
    assert "CA" in page


def test_state_page_shows_its_visits_with_date_and_note(client):
    add_visit(client, "CA", "2024-07-04", "Big Sur road trip")
    page = page_text(client, "/states/CA")
    assert "2024-07-04" in page
    assert "Big Sur road trip" in page


def test_visits_are_listed_newest_first(client):
    """Added out of order on purpose, to prove the page sorts them."""
    add_visit(client, "CA", "2023-05-01", "first")
    add_visit(client, "CA", "2025-01-15", "third")
    add_visit(client, "CA", "2024-07-04", "second")
    page = page_text(client, "/states/CA")
    # .index() gives the position of the text in the page: smaller = higher up.
    assert page.index("third") < page.index("second") < page.index("first")


def test_state_page_only_shows_that_states_visits(client):
    add_visit(client, "CA", "2024-07-04", "California note")
    add_visit(client, "NV", "2024-07-05", "Nevada note")
    page = page_text(client, "/states/CA")
    assert "California note" in page
    assert "Nevada note" not in page


def test_state_without_visits_says_so(client):
    assert "No visits yet." in page_text(client, "/states/WY")


def test_lowercase_code_works_too(client):
    """Typing /states/ca in the address bar should still find California."""
    response = client.get("/states/ca")
    assert response.status_code == 200
    assert "California" in response.get_data(as_text=True)


def test_unknown_state_gives_404(client):
    """404 means "Not Found". D.C. and made-up codes have no page."""
    assert client.get("/states/DC").status_code == 404
    assert client.get("/states/XX").status_code == 404


def test_notes_are_shown_as_text_not_run_as_html(client):
    """A note containing HTML must appear as plain text.

    Otherwise a note like <script>...</script> would run as code in the
    browser. Flask's templates "escape" text to prevent that, and this test
    makes sure it stays that way.
    """
    add_visit(client, "CA", "2024-07-04", "<b>bold</b>")
    page = page_text(client, "/states/CA")
    assert "<b>bold</b>" not in page
    assert "&lt;b&gt;bold&lt;/b&gt;" in page


def test_states_list_links_to_each_state_page(client):
    page = page_text(client, "/states")
    assert 'href="/states/CA"' in page
    assert 'href="/states/WY"' in page
    assert page.count('href="/states/') == 50


def test_state_page_links_to_add_a_visit_for_that_state(client):
    """The link opens the add-visit form with this state already chosen."""
    page = page_text(client, "/states/CA")
    assert 'href="/visits/new?state=CA"' in page

    form = page_text(client, "/visits/new?state=CA")
    assert '<option value="CA" selected' in form


def test_lowercase_state_in_link_is_still_selected(client):
    form = page_text(client, "/visits/new?state=ca")
    assert '<option value="CA" selected' in form


def test_unknown_state_in_link_falls_back_to_the_placeholder(client):
    """Otherwise the browser would quietly pick Alabama."""
    form = page_text(client, "/visits/new?state=XX")
    assert '<option value="" disabled selected>Choose a state</option>' in form
