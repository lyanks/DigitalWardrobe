"""Spaces typed around text are removed before checking and saving."""
from app.extensions import db
from app.models import User
from tests.conftest import login, register
from tests.test_items import add_item, category_id, get_item


def test_spaces_around_the_username_and_email_are_ignored(client):
    page = register(client, username="my_name ", email=" me@example.com ").get_data(as_text=True)
    assert "Letters, numbers, dots and underscores only." not in page
    user = db.session.scalar(db.select(User))
    assert user.username == "my_name" and user.email == "me@example.com"


def test_passwords_keep_their_spaces(client):
    register(client, username="bob", email="bob@example.com", password="Secret123! ")
    client.post("/logout")
    assert b"Log out" not in login(client, "bob", "Secret123!").data
    assert b"Log out" in login(client, "bob", "Secret123! ").data


def test_item_names_are_stripped_too(client):
    register(client)
    add_item(client, name="  White tee  ", category_id=category_id("Tops"), color="white")
    assert get_item("White tee") is not None
