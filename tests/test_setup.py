"""Slice 0: the app starts and its basic wiring works."""


def test_app_uses_temporary_database(app, tmp_path):
    """Tests must use their own database, never the real one in instance/."""
    assert app.config["DATABASE"] == str(tmp_path / "test.sqlite")


def test_states_page_loads(client):
    """The states page answers with HTTP 200 (meaning "OK")."""
    response = client.get("/states")
    assert response.status_code == 200


def test_home_redirects_to_states(client):
    """Opening / sends you on to the states page."""
    response = client.get("/")
    assert response.status_code == 302  # 302 = "go look over there instead"
    assert response.headers["Location"].endswith("/states")
