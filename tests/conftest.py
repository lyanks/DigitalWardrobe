"""Shared test setup. pytest finds fixtures in this file automatically."""
import pytest

from app import create_app
from app.extensions import db
from config import TestConfig


@pytest.fixture
def app(tmp_path):
    class Cfg(TestConfig):
        UPLOAD_FOLDER = str(tmp_path / "uploads")  # throwaway folder per test

    app = create_app(Cfg)
    with app.app_context():
        db.create_all()  # fresh tables in the in-memory database
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    # A fake browser: client.get(...) / client.post(...) without a real server.
    return app.test_client()


def register(client, username="alice", email="alice@example.com", password="secret123"):
    return client.post("/register", data={
        "username": username, "email": email,
        "password": password, "confirm": password,
    }, follow_redirects=True)


def login(client, login="alice", password="secret123"):
    return client.post("/login", data={"login": login, "password": password},
                       follow_redirects=True)


def logout(client):
    return client.post("/logout", follow_redirects=True)
