"""Send an idea: users write, only the admin reads."""
from app.extensions import db
from app.feedback.routes import DAILY_LIMIT
from app.models import Feedback
from tests.conftest import logout, register
from tests.test_admin import admin


def ideas():
    return db.session.scalars(db.select(Feedback).order_by(Feedback.id)).all()


def send(client, text):
    return client.post("/feedback", data={"text": text}, follow_redirects=True)


def test_needs_login(client):
    response = client.get("/feedback")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_user_sends_an_idea(client):
    register(client)
    assert "Send an idea" in client.get("/profile").get_data(as_text=True)
    page = send(client, "  Dark mode for the planner  ").get_data(as_text=True)
    assert "Thank you! Your idea was sent." in page
    [idea] = ideas()
    assert idea.text == "Dark mode for the planner"
    assert idea.author.username == "alice"


def test_empty_idea_is_not_sent(client):
    register(client)
    send(client, "   ")
    assert ideas() == []


def test_daily_limit(client):
    register(client)
    for number in range(DAILY_LIMIT + 2):
        send(client, f"idea {number}")
    assert len(ideas()) == DAILY_LIMIT


def test_only_admin_sees_the_list(client):
    register(client)
    send(client, "More colours please")
    assert client.get("/admin/feedback").status_code == 404
    logout(client)
    admin(client)
    page = client.get("/admin/feedback").get_data(as_text=True)
    assert "More colours please" in page
    assert "alice@example.com" in page


def test_admin_marks_done_and_deletes(client):
    register(client)
    send(client, "Weather please")
    logout(client)
    admin(client)
    idea = ideas()[0]
    client.post(f"/admin/feedback/{idea.id}/done")
    assert idea.done_at is not None
    client.post(f"/admin/feedback/{idea.id}/done")   # and back to new
    assert idea.done_at is None
    client.post(f"/admin/feedback/{idea.id}/delete")
    assert ideas() == []


def test_other_users_cant_mark_or_delete(client):
    register(client)
    send(client, "Keep me")
    idea = ideas()[0]
    assert client.post(f"/admin/feedback/{idea.id}/delete").status_code == 404
    assert len(ideas()) == 1
