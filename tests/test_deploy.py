"""Slice 20: what the PythonAnywhere server needs."""
import sys
from importlib.metadata import version
from pathlib import Path

import tracker

PROJECT = Path(__file__).resolve().parent.parent


def test_requirements_pin_exact_versions():
    """The server installs exactly what was tested here, not "whatever is newest today"."""
    lines = [line.strip() for line in (PROJECT / "requirements.txt").read_text().splitlines() if line.strip()]
    assert lines, "requirements.txt is empty"
    for line in lines:
        assert "==" in line, f"not pinned: {line}"


def test_pinned_flask_is_the_version_tested_here():
    pins = dict(line.strip().split("==") for line in (PROJECT / "requirements.txt").read_text().splitlines()
                if "==" in line)
    assert pins["flask"] == version("flask")
    assert pins["pytest"] == version("pytest")


def test_wsgi_file_loads_the_app_from_app_py(monkeypatch):
    """The ready-to-paste WSGI file must find the project and hand PythonAnywhere `app`.

    It's run here with the project's real folder filled in. create_app is
    replaced by a stand-in, so this test never opens your real database.
    """
    text = (PROJECT / "deploy" / "pythonanywhere_wsgi.py").read_text()
    assert "/home/yourname/50-state-tracker" in text  # the part you replace with your username
    stand_in = object()
    monkeypatch.setattr(tracker, "create_app", lambda: stand_in)
    monkeypatch.delitem(sys.modules, "app", raising=False)  # load app.py fresh
    monkeypatch.setattr(sys, "path", list(sys.path))  # undo the file's sys.path change afterwards

    namespace = {}
    exec(text.replace("/home/yourname/50-state-tracker", str(PROJECT)), namespace)

    assert namespace["application"] is stand_in
    monkeypatch.delitem(sys.modules, "app", raising=False)


def test_set_password_keeps_the_https_only_setting(app, tmp_path):
    """On the server, config.py also holds SESSION_COOKIE_SECURE = True.
    Changing the password later must not drop that line."""
    config = tmp_path / "config.py"
    config.write_text('SESSION_COOKIE_SECURE = True\nSECRET_KEY = "old"\nPASSWORD_HASH = "old"\n')
    app.test_cli_runner().invoke(args=["set-password"], input="new one\nnew one\n")
    text = config.read_text()
    assert "SESSION_COOKIE_SECURE = True" in text
    assert 'SECRET_KEY = "old"' not in text and 'PASSWORD_HASH = "old"' not in text
