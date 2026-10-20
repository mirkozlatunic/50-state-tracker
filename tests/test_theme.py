"""Slice 11: the light/dark switch."""
import re

import pytest

PAGES = ["/states", "/states/CA", "/map", "/visits/new", "/trips", "/trips/new", "/years"]

# The named colors every theme has to define.
COLOR_NAMES = [
    "--bg", "--text", "--muted", "--border", "--link", "--error",
    "--column-bg", "--card-bg", "--visited", "--planned", "--unvisited", "--map-stroke",
]


def css():
    """Helper: the stylesheet as text."""
    with open("tracker/static/style.css") as f:
        return f.read()


def block_after(selector):
    """Helper: the CSS between "<selector> {" and its closing "}" (no nested braces)."""
    match = re.search(re.escape(selector) + r"\s*\{([^{}]*)\}", css())
    return match.group(1) if match else ""


def html_tag(client, url="/states"):
    """Helper: the opening <html ...> tag of a page."""
    page = client.get(url).get_data(as_text=True)
    return re.search(r"<html[^>]*>", page).group(0)


# --- Which theme the page starts in -------------------------------------------------

def test_without_a_saved_choice_the_page_follows_the_device(client):
    """No data-theme attribute: the CSS then picks light or dark from the device setting."""
    assert "data-theme" not in html_tag(client)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_saved_choice_is_written_into_the_page(client, theme):
    """Flask reads the cookie and puts the theme in the HTML, so there's no white flash."""
    client.set_cookie("theme", theme)
    assert f'data-theme="{theme}"' in html_tag(client)


def test_junk_cookie_value_is_ignored(client):
    client.set_cookie("theme", '"><script>alert(1)</script>')
    assert "data-theme" not in html_tag(client)


def test_saved_choice_applies_on_every_page(client):
    client.set_cookie("theme", "dark")
    for url in PAGES:
        assert 'data-theme="dark"' in html_tag(client, url)


# --- The switch -------------------------------------------------------------------------

@pytest.mark.parametrize("url", PAGES)
def test_every_page_has_the_switch_and_its_script(client, url):
    page = client.get(url).get_data(as_text=True)
    header = page.split("<header")[1].split("</header>")[0]
    assert '<button type="button" class="theme-toggle"' in header
    assert 'src="/static/theme.js"' in page


def test_page_says_it_supports_both_themes(client):
    """Lets the browser draw its own parts (scrollbars, date pickers) in the right colors."""
    page = client.get("/states").get_data(as_text=True)
    assert '<meta name="color-scheme" content="light dark">' in page


def test_theme_script_saves_the_choice_in_a_cookie(client):
    script = client.get("/static/theme.js").get_data(as_text=True)
    assert "document.cookie" in script
    assert "data-theme" in script
    assert "prefers-color-scheme" in script  # to know which theme is showing when nothing is saved


# --- The colors -------------------------------------------------------------------------

def test_light_colors_are_defined_once_as_variables():
    light = block_after(":root")
    for name in COLOR_NAMES:
        assert f"{name}:" in light, name


def test_dark_colors_exist_for_a_chosen_dark_theme():
    dark = block_after('[data-theme="dark"]')
    for name in COLOR_NAMES:
        assert f"{name}:" in dark, name
    assert "color-scheme: dark" in dark


def test_dark_colors_also_apply_when_the_device_is_dark_and_nothing_is_saved():
    """Inside @media (prefers-color-scheme: dark), unless you picked light."""
    media = re.search(r"@media \(prefers-color-scheme: dark\) \{(.*?)\n\}", css(), re.S)
    assert media
    assert ':root:not([data-theme="light"])' in media.group(1)
    for name in COLOR_NAMES:
        assert f"{name}:" in media.group(1), name


def test_no_colors_are_hard_coded_outside_the_variables():
    """Every color goes through a variable, so dark mode can't miss one."""
    rest = css()
    rest = re.sub(r"/\*.*?\*/", "", rest, flags=re.S)  # ignore comments
    rest = re.sub(r":root\s*\{[^{}]*\}", "", rest)
    rest = re.sub(r'\[data-theme="dark"\]\s*\{[^{}]*\}', "", rest)
    rest = re.sub(r':root:not\(\[data-theme="light"\]\)\s*\{[^{}]*\}', "", rest)
    leftovers = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgb\(|hsl\(", rest)
    assert leftovers == []


def test_page_and_links_use_the_theme_colors():
    assert "var(--bg)" in block_after("body")
    assert "var(--text)" in block_after("body")
    assert "var(--link)" in block_after("a")
