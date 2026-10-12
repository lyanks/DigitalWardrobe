import io

from app.extensions import db
from app.models import User
from tests.conftest import login, logout, register


def test_register_creates_user_and_logs_in(client):
    response = register(client)

    assert b"Welcome!" in response.data
    assert b"Log out" in response.data
    user = db.session.scalar(db.select(User).filter_by(username="alice"))
    assert user is not None
    assert user.password_hash != "secret123"


def test_register_rejects_duplicate_username_and_email(client):
    register(client)
    logout(client)

    response = register(client, email="other@example.com")
    assert b"That username is taken." in response.data

    response = register(client, username="alice2")
    assert b"An account with that email already exists." in response.data
    assert db.session.query(User).count() == 1


def test_register_rejects_mismatched_passwords(client):
    response = client.post("/register", data={
        "username": "alice", "email": "alice@example.com",
        "password": "secret123", "confirm": "different1",
    })
    assert b"Passwords must match." in response.data
    assert db.session.query(User).count() == 0


def test_login_with_username_or_email(client):
    register(client)
    logout(client)

    assert b"Hi, alice!" in login(client).data
    logout(client)
    assert b"Hi, alice!" in login(client, login="alice@example.com").data


def test_wrong_password_is_rejected(client):
    register(client)
    logout(client)

    response = login(client, password="not-it")
    assert response.status_code == 401
    assert b"Wrong username or password." in response.data
    assert b"Log out" not in response.data


def test_protected_page_redirects_to_login(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert "/login?next=%2Fprofile" in response.headers["Location"]


def test_login_follows_next_but_not_to_other_sites(client):
    register(client)
    logout(client)

    response = client.post("/login?next=/profile",
                           data={"login": "alice", "password": "secret123"})
    assert response.headers["Location"] == "/profile"
    logout(client)

    response = client.post("/login?next=https://evil.example",
                           data={"login": "alice", "password": "secret123"})
    assert response.headers["Location"] == "/"


def test_logout_requires_post(client):
    register(client)
    assert client.get("/logout").status_code == 405
    response = logout(client)
    assert b"You have been logged out." in response.data


def test_two_accounts_see_their_own_profile(client):
    register(client, "alice", "alice@example.com")
    logout(client)
    register(client, "bob", "bob@example.com")

    page = client.get("/profile").data
    assert b"@bob" in page
    assert b"@alice" not in page


def test_edit_display_name_and_upload_avatar(client, app):
    register(client)
    response = client.post("/profile", data={
        "profile-display_name": "Alice A.",
        "profile-avatar": (io.BytesIO(b"fake image bytes"), "me.png"),
        "profile-submit": "Save profile",
    }, content_type="multipart/form-data", follow_redirects=True)

    assert b"Profile saved." in response.data
    user = db.session.scalar(db.select(User).filter_by(username="alice"))
    assert user.display_name == "Alice A."
    assert user.avatar_path.startswith("avatars/") and user.avatar_path.endswith(".png")
    assert "me" not in user.avatar_path  # the original name is not reused
    assert client.get(f"/uploads/{user.avatar_path}").data == b"fake image bytes"


def test_avatar_rejects_non_images(client):
    register(client)
    response = client.post("/profile", data={
        "profile-avatar": (io.BytesIO(b"#!/bin/sh"), "script.sh"),
        "profile-submit": "Save profile",
    }, content_type="multipart/form-data")

    assert b"Images only" in response.data


def test_change_password(client):
    register(client)
    response = client.post("/profile", data={
        "pw-current_password": "wrong-one",
        "pw-new_password": "newsecret1", "pw-confirm": "newsecret1",
        "pw-submit": "Change password",
    })
    assert b"That is not your current password." in response.data

    client.post("/profile", data={
        "pw-current_password": "secret123",
        "pw-new_password": "newsecret1", "pw-confirm": "newsecret1",
        "pw-submit": "Change password",
    })
    logout(client)
    assert login(client, password="secret123").status_code == 401
    assert b"Hi, alice!" in login(client, password="newsecret1").data
