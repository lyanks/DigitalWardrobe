"""The file PythonAnywhere runs to start the app on the server.

It is a copy for reference: the real one lives on PythonAnywhere at
/var/www/YOURNAME_pythonanywhere_com_wsgi.py (open it from the Web tab).
Paste this in there and replace YOURNAME with your PythonAnywhere username.

On your computer `python run.py` starts a small test server. On a real
server a program called a WSGI server (PythonAnywhere uses uWSGI) does that
job instead: it imports this file and looks for a variable called
`application`, then hands every request from a browser to it.
"""
import os
import sys

PROJECT = "/home/YOURNAME/DigitalWardrobe"

# Let Python find the `app` package and config.py in the project folder.
sys.path.insert(0, PROJECT)

# config.py reads SECRET_KEY etc. from the environment the moment it is
# imported, so load the server's .env file first.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(PROJECT, ".env"))

from app import create_app  # noqa: E402

application = create_app()
