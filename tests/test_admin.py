"""The admin pages: only the account with ADMIN_EMAIL gets in."""
from app.extensions import db
from app.models import InviteCode
from tests.conftest import logout, register


def admin(client):
    register(client, "boss", "boss@example.com")


def test_visitors_and_other_users_get_page_not_found(client):
    assert client.get("/admin/invites").status_code == 404
    register(client)
    assert client.get("/admin").status_code == 404
    assert client.get("/admin/invites").status_code == 404
    assert client.post("/admin/invites", data={"note": "x"}).status_code == 404
    assert db.session.scalar(db.select(InviteCode).filter_by(note="x")) is None


def test_same_email_in_other_capitals_is_one_account(client):
    # Emails are saved in lowercase, so BOSS@... is the same (taken) address.
    admin(client)
    logout(client)
    register(client, "boss2", "BOSS@example.com")
    assert client.get("/admin/invites").status_code == 404


def test_no_admin_email_means_no_admin(app, client):
    app.config["ADMIN_EMAIL"] = ""
    admin(client)
    assert client.get("/admin/invites").status_code == 404


def test_admin_link_only_for_the_admin(client):
    register(client)
    assert ">Admin<" not in client.get("/").get_data(as_text=True)
    logout(client)
    admin(client)
    assert ">Admin<" in client.get("/").get_data(as_text=True)


def test_admin_makes_and_turns_off_codes(client):
    admin(client)
    page = client.post("/admin/invites", data={"note": "for Olena", "expires_on": "31.12.2026"},
                       follow_redirects=True).get_data(as_text=True)
    invite = db.session.scalar(db.select(InviteCode).filter_by(note="for Olena"))
    assert f"New code: {invite.code}" in page
    assert "works until 31.12.2026" in page

    client.post(f"/admin/invites/{invite.id}/off")
    db.session.refresh(invite)
    assert invite.disabled_at is not None
    assert "Turned off" in client.get("/admin/invites").get_data(as_text=True)


def test_admin_sees_who_used_a_code(client):
    admin(client)
    client.post("/admin/invites", data={"note": "for Alice"})
    invite = db.session.scalar(db.select(InviteCode).filter_by(note="for Alice"))
    logout(client)
    register(client, code=invite.code)
    logout(client)
    from tests.conftest import login
    login(client, "boss")
    page = client.get("/admin/invites").get_data(as_text=True)
    assert "Used by alice (alice@example.com) on" in page
