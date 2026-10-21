"""Invite-only sign-up."""
from datetime import date, timedelta

from app.extensions import db
from app.invites import create_invite, tidy
from app.models import InviteCode, User, utcnow
from tests.conftest import logout, register
from tests.test_auth import fake_google


def users():
    return db.session.scalar(db.select(db.func.count()).select_from(User))


def test_sign_up_without_a_code_is_refused(client):
    page = register(client, code="").get_data(as_text=True)
    assert users() == 0
    assert "This field is required." in page


def test_made_up_code_is_refused(client):
    page = register(client, code="WARD-AAAA-BBBB").get_data(as_text=True)
    assert users() == 0
    assert "This invite code isn't valid." in page


def test_a_code_works_once_and_remembers_who_used_it(client):
    invite = create_invite("for Alice")
    register(client, code=invite.code)
    assert users() == 1
    db.session.refresh(invite)
    assert invite.used_by.username == "alice"
    assert invite.used_at is not None

    logout(client)
    page = register(client, "bob", "bob@example.com", code=invite.code).get_data(as_text=True)
    assert users() == 1
    assert "This invite code isn't valid." in page


def test_code_can_be_typed_loosely(client):
    invite = create_invite()
    register(client, code=" " + invite.code.lower().replace("-", " "))
    assert users() == 1
    assert tidy("ward7kq2m9xd") == "WARD-7KQ2-M9XD"


def test_turned_off_and_expired_codes_are_refused(client):
    off = create_invite()
    off.disabled_at = utcnow()
    old = create_invite(expires_on=date.today() - timedelta(days=1))
    db.session.commit()
    register(client, code=off.code)
    register(client, code=old.code)
    assert users() == 0


def test_code_works_on_its_last_day(client):
    invite = create_invite(expires_on=date.today())
    register(client, code=invite.code)
    assert users() == 1


def test_new_google_account_needs_a_code(client, monkeypatch):
    fake_google(monkeypatch)
    page = client.get("/login/google/callback", follow_redirects=True).get_data(as_text=True)
    assert users() == 0
    assert "enter your invite code on the sign-up page first" in page


def test_google_button_on_sign_up_checks_the_code(client):
    response = client.post("/login/google", data={"invite_code": "nope"})
    assert response.headers["Location"].endswith("/register")
    from unittest.mock import patch
    from app.extensions import oauth
    invite = create_invite()
    with patch.object(oauth.google, "authorize_redirect", return_value=("redirected", 302)):
        client.post("/login/google", data={"invite_code": invite.code.lower()})
    with client.session_transaction() as session:
        assert session["invite_code"] == invite.code


def test_existing_google_account_logs_in_without_a_code(client, monkeypatch):
    register(client, "anna", "anna@gmail.com")
    logout(client)
    fake_google(monkeypatch)
    page = client.get("/login/google/callback", follow_redirects=True).get_data(as_text=True)
    assert "Hi, anna!" in page


def test_flask_invites_create(app):
    output = app.test_cli_runner().invoke(args=["invites", "create", "--note", "Olena"]).output
    invite = db.session.scalar(db.select(InviteCode))
    assert output.strip() == invite.code
    assert invite.note == "Olena"
