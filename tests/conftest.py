"""Shared test setup. pytest finds fixtures in this file automatically."""
import io

import pytest
from PIL import Image

from app import create_app
from app.extensions import db
from config import TestConfig
from seed import seed_categories, seed_options


@pytest.fixture
def app(tmp_path):
    class Cfg(TestConfig):
        UPLOAD_FOLDER = str(tmp_path / "uploads")  # throwaway folder per test

    app = create_app(Cfg)

    # A real server starts every request with a fresh `g`. The tests share
    # one app context, so drop what the last request kept in it: the
    # shared lists (app/options.py) and the language (Flask-Babel).
    from flask_babel import refresh
    from app.options import forget
    app.before_request(forget)
    app.before_request(refresh)

    with app.app_context():
        db.create_all()  # fresh tables in the in-memory database
        seed_categories()
        seed_options()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    # A fake browser: client.get(...) / client.post(...) without a real server.
    return app.test_client()


def register(client, username="alice", email="alice@example.com", password="Secret123!",
             skip_setup=True, code=None):
    # Sign-up needs an invite code: make a fresh one unless the test brings its own.
    if code is None:
        from app.invites import create_invite
        code = create_invite().code
    response = client.post("/register", data={
        "invite_code": code, "username": username, "email": email,
        "password": password, "confirm": password,
    }, follow_redirects=True)
    if skip_setup:
        # Most tests aren't about the setup wizard (idea #7): finish it the
        # quick way, like pressing "Skip the setup".
        client.post("/welcome/skip")
    return response


def google_invite(client):
    """Put an invite code in the session, like the Google button on the sign-up page does."""
    from app.invites import create_invite
    code = create_invite().code
    with client.session_transaction() as session:
        session["invite_code"] = code
    return code


def login(client, login="alice", password="Secret123!"):
    return client.post("/login", data={"login": login, "password": password},
                       follow_redirects=True)


def logout(client):
    return client.post("/logout", follow_redirects=True)


def make_image(name="photo.png", size=(60, 40), color="red"):
    """A real (tiny) image file in memory, ready to upload in a test."""
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    buffer.seek(0)
    return buffer, name
