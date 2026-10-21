# The WSGI file for PythonAnywhere: paste this into the file linked on the
# Web tab, and replace "yourname" with your PythonAnywhere username.
#
# WSGI is how a web server starts a Python web app: it imports this file and
# uses the object called `application`.
import sys

PROJECT = "/home/yourname/50-state-tracker"
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

from app import app as application  # noqa: E402  (the import has to come after the path)
