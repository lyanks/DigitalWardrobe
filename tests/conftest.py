"""Shared test setup. pytest finds fixtures in this file automatically."""
import io

import pytest
from PIL import Image

from app import create_app
from app.extensions import db
from config import TestConfig
from seed import seed_categories


@pytest.fixture
def app(tmp_path):
    class Cfg(TestConfig):
        UPLOAD_FOLDER = str(tmp_path / "uploads")  # throwaway folder per test

    app = create_app(Cfg)
    with app.app_context():
        db.create_all()  # fresh tables in the in-memory database
        seed_categories()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    # A fake browser: client.get(...) / client.post(...) without a real server.
    return app.test_client()


def register(client, username="alice", email="alice@example.com", password="Secret123!",
             skip_setup=True):
    response = client.post("/register", data={
        "username": username, "email": email,
        "password": password, "confirm": password,
    }, follow_redirects=True)
    if skip_setup:
        # Most tests aren't about the setup wizard (idea #7): finish it the
        # quick way, like pressing "Skip the setup".
        client.post("/welcome/skip")
    return response


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
