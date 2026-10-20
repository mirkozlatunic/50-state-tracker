"""Entry point for `flask run`.

Flask looks for a file called app.py and an object called `app` in it, so this
file lets you start the server with plain `flask run`.
"""
from tracker import create_app

app = create_app()
