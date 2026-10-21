"""The tutorial page and the "New here?" banner that suggests it."""
from app.extensions import db
from app.models import User
from tests.conftest import register


def alice():
    return db.session.scalar(db.select(User).filter_by(username="alice"))


def test_visitors_can_read_the_tutorial(client):
    page = client.get("/tutorial").get_data(as_text=True)
    assert "How it works" in page and "Pack a suitcase" in page
    assert "Try it as a guest" in page
    assert "See how it works" in client.get("/").get_data(as_text=True)  # landing link


def test_new_users_get_the_banner_until_they_open_the_tutorial(client):
    register(client)
    assert "New here?" in client.get("/").get_data(as_text=True)
    page = client.get("/tutorial").get_data(as_text=True)
    assert "Open the planner" in page  # the "Open" links are for logged-in users
    assert alice().tutorial_seen_at is not None
    assert "New here?" not in client.get("/").get_data(as_text=True)


def test_closing_the_banner_hides_it_for_good(client):
    register(client)
    response = client.post("/tutorial/hide", follow_redirects=True)
    assert "New here?" not in response.get_data(as_text=True)
    assert alice().tutorial_seen_at is not None
    # Still reachable from the profile page.
    assert "/tutorial" in client.get("/profile").get_data(as_text=True)


def test_hide_needs_a_login(client):
    assert client.post("/tutorial/hide").status_code == 302
