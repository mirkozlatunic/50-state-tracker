"""Slice 10: pages that work on an iPhone and a tablet.

pytest can't see how a page looks on a screen, so these tests check the
building blocks: the HTML structure and the CSS rules. How it really looks is
checked in a browser at iPhone and iPad sizes.
"""
import re

import pytest

from tracker.models import add_trip

# Every page with the shared layout. The edit page needs a trip, made in the fixture below.
PAGES = ["/states", "/states/CA", "/map", "/visits/new", "/trips", "/trips/new", "/trips/1/edit", "/years"]


@pytest.fixture
def client_with_trip(app, client):
    """A test client whose database has one trip (id 1), so /trips/1/edit exists."""
    with app.app_context():
        add_trip("Weekend", "2099-06-01", "2099-06-02", ["VT"])
    return client


def css():
    """Helper: the stylesheet as text."""
    with open("tracker/static/style.css") as f:
        return f.read()


def media_block(width):
    """Helper: the CSS inside "@media (max-width: <width>)", or "" if there's none.

    Grabs everything from that line up to the next "@media" (or the end).
    """
    match = re.search(rf"@media \(max-width: {width}\) \{{(.*?)(?=\n@media|\Z)", css(), re.S)
    return match.group(1) if match else ""


# --- On every page ---------------------------------------------------------------

@pytest.mark.parametrize("url", PAGES)
def test_every_page_tells_phones_to_use_their_real_width(client_with_trip, url):
    """Without this tag, an iPhone pretends to be a 980px-wide desktop and shrinks everything.

    @pytest.mark.parametrize runs this test once for each address in PAGES.
    """
    page = client_with_trip.get(url).get_data(as_text=True)
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in page


@pytest.mark.parametrize("url", PAGES)
def test_every_page_has_the_two_row_header(client_with_trip, url):
    """Row 1: brand and counter. Row 2: the nav, which can wrap on a phone."""
    page = client_with_trip.get(url).get_data(as_text=True)
    header = page.split("<header")[1].split("</header>")[0]
    top = header.split('class="header-top"')[1].split('<nav class="site-nav"')[0]
    assert 'class="brand"' in top
    assert 'class="progress"' in top
    assert '<nav class="site-nav"' in header


# --- The CSS rules ------------------------------------------------------------------

def test_there_are_phone_and_tablet_rules():
    """640px and narrower = phone; 1024px and narrower = tablet (an iPad is 820px)."""
    assert media_block("640px")
    assert media_block("1024px")


def test_counter_never_breaks_onto_two_lines():
    """"7 of 50" must stay together, not "7 of" / "50"."""
    progress_rule = re.search(r"\.progress \{(.*?)\}", css(), re.S).group(1)
    assert "white-space: nowrap" in progress_rule


def test_form_fields_use_16px_text():
    """iPhone Safari zooms in on any field with smaller text when you tap it."""
    rule = re.search(r"input,\s*select,\s*textarea,\s*button \{(.*?)\}", css(), re.S).group(1)
    assert "font-size: 16px" in rule


def test_tap_targets_are_at_least_44px_on_touch_screens():
    """Apple's guideline for something you tap with a finger. Only on touch screens,
    so the desktop layout stays compact. (pointer: coarse) means "a finger, not a mouse"."""
    match = re.search(r"@media \(pointer: coarse\) \{(.*?)\n\}", css(), re.S)
    assert match and "min-height: 44px" in match.group(1)


def test_year_columns_stack_on_a_phone():
    phone = media_block("640px")
    assert re.search(r"\.years \{[^}]*flex-direction: column", phone)


def test_year_columns_go_two_by_two_on_a_tablet():
    tablet = media_block("1024px")
    assert re.search(r"\.year \{[^}]*flex: 1 0 calc\(50% - 0\.5rem\)", tablet)


def test_trip_form_checkboxes_use_two_columns_on_a_phone():
    phone = media_block("640px")
    assert re.search(r"\.state-checkboxes \{[^}]*grid-template-columns: 1fr 1fr", phone)


# --- The year page on a phone -------------------------------------------------------

def test_year_page_explains_the_move_menu_for_phones(client):
    """Dragging with a finger isn't reliable on an iPhone, so phones get a different hint.
    Both hints are in the page; the CSS shows the right one for the screen."""
    page = client.get("/years").get_data(as_text=True)
    assert 'class="hint drag-hint"' in page
    assert 'class="hint touch-hint"' in page
    assert "Tap “Move to” on a trip" in page
