import io

from app.extensions import db
from app.models import User
from tests.conftest import login, logout, make_image, register


def test_register_creates_user_and_logs_in(client):
    response = register(client)

    assert b"Welcome!" in response.data
    assert b"Log out" in response.data
    user = db.session.scalar(db.select(User).filter_by(username="alice"))
    assert user is not None
    assert user.password_hash != "Secret123!"


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
        "password": "Secret123!", "confirm": "Different1!",
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
                           data={"login": "alice", "password": "Secret123!"})
    assert response.headers["Location"] == "/profile"
    logout(client)

    response = client.post("/login?next=https://evil.example",
                           data={"login": "alice", "password": "Secret123!"})
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
        "profile-username": "alice",
        "profile-display_name": "Alice A.",
        "profile-avatar": make_image("me.png"),
        "profile-submit": "Save profile",
    }, content_type="multipart/form-data", follow_redirects=True)

    assert b"Profile saved." in response.data
    user = db.session.scalar(db.select(User).filter_by(username="alice"))
    assert user.display_name == "Alice A."
    # Saved as JPEG under a random name; the original name is not reused.
    assert user.avatar_path.startswith("avatars/") and user.avatar_path.endswith(".jpg")
    assert "me" not in user.avatar_path
    response = client.get(f"/uploads/{user.avatar_path}")
    assert response.status_code == 200
    assert response.mimetype == "image/jpeg"


def test_avatar_rejects_non_images(client):
    register(client)
    response = client.post("/profile", data={
        "profile-avatar": (io.BytesIO(b"#!/bin/sh"), "script.sh"),
        "profile-submit": "Save profile",
    }, content_type="multipart/form-data")

    assert b"Images only" in response.data


def test_avatar_rejects_fake_image_with_image_name(client):
    register(client)
    response = client.post("/profile", data={
        "profile-username": "alice",
        "profile-display_name": "Should not be saved",
        "profile-avatar": (io.BytesIO(b"not really a png"), "sneaky.png"),
        "profile-submit": "Save profile",
    }, content_type="multipart/form-data")

    assert b"not a readable image" in response.data
    user = db.session.scalar(db.select(User).filter_by(username="alice"))
    assert user.avatar_path is None
    assert user.display_name is None


def test_change_password(client):
    register(client)
    response = client.post("/profile", data={
        "pw-current_password": "wrong-one",
        "pw-new_password": "NewSecret1?", "pw-confirm": "NewSecret1?",
        "pw-submit": "Change password",
    })
    assert b"That is not your current password." in response.data

    client.post("/profile", data={
        "pw-current_password": "Secret123!",
        "pw-new_password": "NewSecret1?", "pw-confirm": "NewSecret1?",
        "pw-submit": "Change password",
    })
    logout(client)
    assert login(client, password="Secret123!").status_code == 401
    assert b"Hi, alice!" in login(client, password="NewSecret1?").data


# ---------- strong passwords ----------

def test_weak_password_lists_what_is_missing(client):
    response = register(client, password="secret123")
    assert b"Password needs an uppercase letter and a special character" in response.data
    assert db.session.query(User).count() == 0


def test_missing_rules():
    from app.auth.validators import missing_rules
    assert missing_rules("Abc1!") == ["at least 8 characters"]
    assert missing_rules("ABCDEFG1!") == ["a lowercase letter"]
    assert missing_rules("Good-Pass9") == []
    assert len(missing_rules("")) == 5


def test_new_password_must_be_strong_too(client):
    register(client)
    response = client.post("/profile", data={
        "pw-current_password": "Secret123!",
        "pw-new_password": "password", "pw-confirm": "password",
        "pw-submit": "Change password",
    })
    assert b"Password needs" in response.data


# ---------- Sign in with Google ----------

def fake_google(monkeypatch, **userinfo):
    """Pretend Google answered with this person, without any network."""
    from app.extensions import oauth
    info = {"sub": "google-123", "email": "anna@gmail.com", "email_verified": True,
            "name": "Anna K"}
    info.update(userinfo)
    monkeypatch.setattr(oauth.google, "authorize_access_token", lambda: {"userinfo": info})


def test_google_button_shows_when_configured(client):
    assert b"Continue with Google" in client.get("/login").data


def test_google_login_redirects_to_google(client):
    from unittest.mock import patch
    from app.extensions import oauth
    with patch.object(oauth.google, "authorize_redirect",
                      return_value=("redirected", 302)) as redirect_mock:
        client.get("/login/google")
    callback = redirect_mock.call_args.args[0]
    assert callback == "http://localhost/login/google/callback"


def test_google_creates_new_account(client, monkeypatch):
    fake_google(monkeypatch)
    response = client.get("/login/google/callback", follow_redirects=True)

    assert b"Hi, Anna K!" in response.data
    user = db.session.scalar(db.select(User).filter_by(google_id="google-123"))
    assert user.username == "anna"
    assert user.email == "anna@gmail.com"
    assert not user.has_password
    # No password can ever match a Google-only account.
    logout(client)
    assert login(client, login="anna", password="").status_code != 302


def test_google_links_existing_account_with_same_email(client, monkeypatch):
    register(client, "alice", "alice@gmail.com")
    logout(client)
    fake_google(monkeypatch, email="Alice@gmail.com", sub="google-999")

    client.get("/login/google/callback")
    assert db.session.query(User).count() == 1
    user = db.session.scalar(db.select(User).filter_by(username="alice"))
    assert user.google_id == "google-999"
    assert user.has_password  # old password still works too


def test_google_username_is_made_unique(client, monkeypatch):
    register(client, "anna", "anna@example.com")
    logout(client)
    fake_google(monkeypatch)  # anna@gmail.com, a different email
    client.get("/login/google/callback")
    assert db.session.scalar(db.select(User).filter_by(google_id="google-123")).username == "anna2"


def test_google_rejects_unverified_email(client, monkeypatch):
    fake_google(monkeypatch, email_verified=False)
    response = client.get("/login/google/callback", follow_redirects=True)
    assert b"isn&#39;t verified" in response.data
    assert db.session.query(User).count() == 0


def test_google_user_can_set_a_password(client, monkeypatch):
    fake_google(monkeypatch)
    client.get("/login/google/callback")
    page = client.get("/profile").data
    assert b"Set a password" in page and b"Current password" not in page

    client.post("/profile", data={
        "pw-new_password": "Wardrobe1!", "pw-confirm": "Wardrobe1!",
        "pw-submit": "Change password",
    })
    logout(client)
    assert b"Hi, Anna K!" in login(client, login="anna", password="Wardrobe1!").data


# ---------- changing the username ----------

def save_profile(client, **fields):
    data = {"profile-username": "alice", "profile-submit": "Save profile"}
    data.update({f"profile-{k}": v for k, v in fields.items()})
    return client.post("/profile", data=data, follow_redirects=True)


def test_change_username_and_log_in_with_it(client):
    register(client)
    assert b'value="alice"' in client.get("/profile").data  # pre-filled

    response = save_profile(client, username="alice_k")
    assert b"Profile saved." in response.data
    logout(client)
    assert b"Hi, alice_k!" in login(client, login="alice_k").data
    logout(client)
    assert login(client, login="alice").status_code == 401  # old name is gone


def test_change_username_rules(client):
    register(client, "bob", "bob@example.com")
    logout(client)
    register(client)

    assert b"That username is taken." in save_profile(client, username="bob").data
    assert b"Letters, numbers" in save_profile(client, username="bad name!").data
    assert b"Profile saved." in save_profile(client, username="alice").data  # own name is fine
    assert db.session.scalar(db.select(User).filter_by(email="alice@example.com")).username == "alice"


def test_google_user_can_rename(client, monkeypatch):
    fake_google(monkeypatch, email="lyanka.k.2004@gmail.com")
    client.get("/login/google/callback")
    response = client.post("/profile", data={
        "profile-username": "lyanks", "profile-submit": "Save profile",
    }, follow_redirects=True)
    assert b"@lyanks" in response.data
