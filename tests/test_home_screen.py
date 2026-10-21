"""Slice 17: add the app to the iPhone home screen (a "web app manifest" and icons)."""
import json
import struct

import pytest

PAGES = ["/states", "/states/CA", "/map", "/visits/new", "/trips", "/trips/new", "/years"]


def png_size(data):
    """Helper: (width, height) of a PNG image, read from its header.

    Every PNG starts with the same 8 "signature" bytes; the width and height
    follow at bytes 16-24, as two 4-byte numbers (struct.unpack reads them).
    """
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG file"
    return struct.unpack(">II", data[16:24])


def manifest(client):
    """Helper: the manifest, read as JSON."""
    return json.loads(client.get("/manifest.webmanifest").get_data(as_text=True))


# --- The manifest: what the phone reads when you add the app ---------------------------

def test_manifest_is_served_as_a_manifest(client):
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response.content_type.startswith("application/manifest+json")


def test_manifest_names_the_app_and_opens_full_screen_on_the_map(client):
    data = manifest(client)
    assert data["name"] == "50 States Tracker"
    assert data["short_name"] == "50 States"  # the name under the icon
    assert data["start_url"] == "/map"
    assert data["scope"] == "/"
    assert data["display"] == "standalone"    # full screen, no browser bars
    assert data["background_color"] and data["theme_color"]


@pytest.mark.parametrize("size", [192, 512])
def test_manifest_icons_exist_at_their_size(client, size):
    icon = next(i for i in manifest(client)["icons"] if i["sizes"] == f"{size}x{size}")
    assert icon["type"] == "image/png"
    response = client.get(icon["src"])
    assert response.status_code == 200
    assert png_size(response.data) == (size, size)


# --- Icons for the home screen and the browser tab --------------------------------------

def test_iphone_home_screen_icon_is_180_pixels(client):
    response = client.get("/static/icons/icon-180.png")
    assert png_size(response.data) == (180, 180)


def test_browser_tab_icon_is_32_pixels(client):
    response = client.get("/static/icons/favicon-32.png")
    assert png_size(response.data) == (32, 32)


def test_favicon_ico_no_longer_gives_404(client):
    """Browsers ask for /favicon.ico by themselves; that used to be a 404."""
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.content_type == "image/png"
    assert png_size(response.data) == (32, 32)


# --- The tags on every page -------------------------------------------------------------

@pytest.mark.parametrize("url", PAGES)
def test_every_page_links_the_manifest_and_icons(client, url):
    page = client.get(url).get_data(as_text=True)
    head = page.split("</head>")[0]
    assert '<link rel="manifest" href="/manifest.webmanifest">' in head
    assert '<link rel="apple-touch-icon" href="/static/icons/icon-180.png">' in head
    assert '<link rel="icon" type="image/png" href="/static/icons/favicon-32.png">' in head


@pytest.mark.parametrize("url", PAGES)
def test_every_page_can_run_full_screen_with_its_name(client, url):
    head = client.get(url).get_data(as_text=True).split("</head>")[0]
    assert '<meta name="apple-mobile-web-app-capable" content="yes">' in head
    assert '<meta name="mobile-web-app-capable" content="yes">' in head
    assert '<meta name="apple-mobile-web-app-title" content="50 States">' in head


def test_top_bar_color_follows_light_and_dark(client):
    """theme-color colors the phone's top bar; one for each theme."""
    head = client.get("/states").get_data(as_text=True).split("</head>")[0]
    assert '<meta name="theme-color" media="(prefers-color-scheme: light)"' in head
    assert '<meta name="theme-color" media="(prefers-color-scheme: dark)"' in head
