"""Guest mode: everything works, nothing reaches the real database."""
import os
import time

from app import guests
from app.extensions import db
from app.models import Item, User
from tests.conftest import make_image, register
from tests.test_items import category_id


def real_counts():
    """Rows in every table of the real database."""
    return {table.name: db.session.scalar(db.select(db.func.count()).select_from(table))
            for table in db.metadata.sorted_tables}


def try_as_guest(client):
    return client.post("/guest", follow_redirects=True)


def guest_files(app):
    return [name for name in os.listdir(app.config["GUEST_FOLDER"]) if name.endswith(".db")]


def test_try_as_guest_shows_the_bar_and_samples(client):
    before = real_counts()
    page = try_as_guest(client).get_data(as_text=True)
    assert "Guest mode." in page
    assert "Nothing you do here is saved." in page
    wardrobe = client.get("/items").get_data(as_text=True)
    assert "Blue jeans" in wardrobe and "White sneakers" in wardrobe
    assert real_counts() == before


def test_everything_a_guest_does_stays_out_of_the_real_database(app, client):
    register(client, "alice", "alice@example.com")  # a real account, id 1
    client.post("/logout")
    before = real_counts()

    guest = app.test_client()
    try_as_guest(guest)
    guest.post("/items/new", data={
        "name": "Guest coat", "category_id": category_id("Outerwear"), "color": "green",
        "season": "winter", "style": "", "photo": make_image(),
    }, content_type="multipart/form-data")
    coat_page = guest.get("/items").get_data(as_text=True)
    assert "Guest coat" in coat_page
    guest.post("/outfits/new", data={"name": "Guest look", "item_ids": [1, 3]})
    guest.post("/trips", data={"name": "Lviv", "start_date": "01.11.2026", "end_date": "03.11.2026"})
    guest.post("/language/uk")
    guest.post("/profile", data={"profile-username": "visitor", "profile-submit": "Save profile"})
    guest.get("/stats")
    guest.get("/planner")

    assert real_counts() == before
    assert db.session.scalar(db.select(Item).filter_by(name="Guest coat")) is None
    assert db.session.scalar(db.select(User).filter_by(username="visitor")) is None
    # The guest's photo is in the guest folder, not in the real uploads.
    assert not os.path.exists(os.path.join(app.config["UPLOAD_FOLDER"], "items"))


def test_same_ids_never_mix(app, client):
    register(client, "alice", "alice@example.com")
    guest = app.test_client()
    try_as_guest(guest)
    assert "Guest" in guest.get("/profile").get_data(as_text=True)
    assert "alice@example.com" not in guest.get("/profile").get_data(as_text=True)
    assert "alice@example.com" in client.get("/profile").get_data(as_text=True)


def test_two_guests_dont_see_each_other(app):
    one, two = app.test_client(), app.test_client()
    try_as_guest(one)
    try_as_guest(two)
    one.post("/items/new", data={"name": "Only mine", "category_id": category_id("Tops"),
                                 "color": "red", "season": "all", "style": ""},
             content_type="multipart/form-data")
    assert "Only mine" in one.get("/items").get_data(as_text=True)
    assert "Only mine" not in two.get("/items").get_data(as_text=True)


def test_leave_deletes_everything(app, client):
    try_as_guest(client)
    assert len(guest_files(app)) == 1
    page = client.post("/guest/leave", follow_redirects=True).get_data(as_text=True)
    assert guest_files(app) == []
    assert "Guest mode." not in page
    assert client.get("/items").status_code == 302  # logged out


def test_an_hour_without_activity_ends_the_visit(app, client):
    try_as_guest(client)
    path = os.path.join(app.config["GUEST_FOLDER"], guest_files(app)[0])
    two_hours_ago = time.time() - 2 * 60 * 60
    os.utime(path, (two_hours_ago, two_hours_ago))
    guests.clean_up(force=True)
    assert guest_files(app) == []
    page = client.get("/items", follow_redirects=True).get_data(as_text=True)
    assert "Your guest visit has ended" in page


def test_activity_keeps_the_visit(app, client):
    try_as_guest(client)
    path = os.path.join(app.config["GUEST_FOLDER"], guest_files(app)[0])
    ten_minutes_ago = time.time() - 10 * 60
    os.utime(path, (ten_minutes_ago, ten_minutes_ago))
    client.get("/items")
    assert time.time() - os.path.getmtime(path) < 5


def test_guests_cannot_open_admin(app, client):
    try_as_guest(client)
    # Even if ADMIN_EMAIL were the guest's made-up email, a guest gets nothing.
    import sqlite3
    path = os.path.join(app.config["GUEST_FOLDER"], guest_files(app)[0])
    app.config["ADMIN_EMAIL"] = sqlite3.connect(path).execute("SELECT email FROM user").fetchone()[0]
    assert client.get("/admin").status_code == 404
    assert client.get("/admin/invites").status_code == 404


def test_guests_have_no_password_to_change(client):
    try_as_guest(client)
    assert "Change password" not in client.get("/profile").get_data(as_text=True)
    assert "Set a password" not in client.get("/profile").get_data(as_text=True)


def test_photo_limit(client, monkeypatch):
    monkeypatch.setattr(guests, "MAX_PHOTOS", 1)
    try_as_guest(client)

    def add(name):
        return client.post("/items/new", data={
            "name": name, "category_id": category_id("Tops"), "color": "red",
            "season": "all", "style": "", "photo": make_image(),
        }, content_type="multipart/form-data", follow_redirects=True).get_data(as_text=True)

    add("First")
    assert "Guests can add up to 1 photos." in add("Second")


def test_oldest_guest_makes_room(app, monkeypatch):
    monkeypatch.setattr(guests, "MAX_GUESTS", 2)
    for _ in range(3):
        try_as_guest(app.test_client())
    assert len(guest_files(app)) == 2


def test_a_guest_can_go_and_sign_up(client):
    try_as_guest(client)
    response = client.post("/guest/leave", data={"next": "register"})
    assert response.headers["Location"].endswith("/register")
    register(client)
    assert db.session.scalar(db.select(User).filter_by(username="alice")) is not None


def test_google_button_ends_the_guest_visit_first(app, client):
    from unittest.mock import patch
    from app.extensions import oauth
    try_as_guest(client)
    with patch.object(oauth.google, "authorize_redirect", return_value=("redirected", 302)):
        client.get("/login/google")
    assert guest_files(app) == []
