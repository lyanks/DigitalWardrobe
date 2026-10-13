"""Idea #5: themes and an accent colour."""
from app.extensions import db
from app.models import User
from app.themes import text_on
from tests.conftest import register


def save_look(client, theme="midnight", accent="#c4a8ff", use_theme_accent=True):
    data = {"look-theme": theme, "look-accent_color": accent, "look-submit": "Save look"}
    if use_theme_accent:
        data["look-use_theme_accent"] = "y"
    return client.post("/profile", data=data, follow_redirects=True)


def user():
    return db.session.scalar(db.select(User).filter_by(username="alice"))


def test_new_accounts_and_visitors_get_midnight(client):
    assert 'data-theme="midnight"' in client.get("/").get_data(as_text=True)
    register(client)
    assert user().theme == "midnight" and user().accent_color is None
    assert 'data-theme="midnight"' in client.get("/items").get_data(as_text=True)


def test_pick_a_theme(client):
    register(client)
    page = save_look(client, theme="linen").get_data(as_text=True)
    assert "Your new look is saved." in page
    assert user().theme == "linen"
    assert 'data-theme="linen"' in client.get("/items").get_data(as_text=True)


def test_custom_accent_colour_goes_on_every_page(client):
    register(client)
    save_look(client, theme="lavender", accent="#2F5D8A", use_theme_accent=False)
    assert user().accent_color == "#2f5d8a"
    page = client.get("/items").get_data(as_text=True)
    assert "--color-primary: #2f5d8a" in page
    assert "--color-on-primary: #ffffff" in page   # white text on dark blue


def test_back_to_the_theme_colour(client):
    register(client)
    save_look(client, accent="#2f5d8a", use_theme_accent=False)
    save_look(client, use_theme_accent=True)
    assert user().accent_color is None
    assert "--color-primary" not in client.get("/items").get_data(as_text=True)


def test_unknown_theme_and_bad_colour_are_refused(client):
    register(client)
    save_look(client, theme="neon")
    save_look(client, accent="red", use_theme_accent=False)
    assert user().theme == "midnight" and user().accent_color is None


def test_text_on_picks_a_readable_colour():
    assert text_on("#ffffff") == "#1d0b3a"
    assert text_on("#c4a8ff") == "#1d0b3a"   # light lavender: dark text
    assert text_on("#6157ae") == "#ffffff"   # deep purple: white text
    assert text_on("#000000") == "#ffffff"
