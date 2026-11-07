"""The "Suggest a look" page, the save button and the profile fields."""
from app.models import User
from app.extensions import db
from tests.conftest import login, logout, register
from tests.test_outfits import get_outfit, ids, make_basics


def test_suggest_needs_login(client):
    response = client.get("/outfits/suggest")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_empty_wardrobe_asks_for_clothes(client):
    register(client)
    assert b"Add a few clothes first" in client.get("/outfits/suggest").data


def test_suggests_looks_from_my_clothes(client):
    register(client)
    make_basics(client)
    page = client.get("/outfits/suggest?season=summer").data
    assert b"Save as outfit" in page
    assert b"White tee" in page or b"Red dress" in page
    # The outfits page has the button.
    assert b"Suggest a look" in client.get("/outfits").data


def test_save_a_suggestion(client):
    register(client)
    make_basics(client)
    response = client.post("/outfits/suggest/save", data={
        "name": "Sunny day", "item_ids": ",".join(map(str, ids("White tee", "Blue jeans", "Sneakers"))),
    }, follow_redirects=True)
    assert "Saved the outfit “Sunny day”.".encode() in response.data
    assert [item.name for item in get_outfit("Sunny day").items] == ["White tee", "Blue jeans", "Sneakers"]


def test_cant_save_someone_elses_clothes(client):
    register(client)
    make_basics(client)
    alice_ids = ids("White tee", "Blue jeans")
    logout(client)
    register(client, username="bob", email="bob@example.com")
    client.post("/outfits/suggest/save", data={
        "name": "Stolen", "item_ids": ",".join(map(str, alice_ids)),
    })
    assert get_outfit("Stolen") is None


def test_profile_saves_undertone_and_body_shape(client):
    register(client)
    client.post("/profile", data={
        "suggest-undertone": "warm", "suggest-body_shape": "pear", "suggest-submit": "Save",
    }, follow_redirects=True)
    user = db.session.scalar(db.select(User).filter_by(username="alice"))
    assert (user.undertone, user.body_shape) == ("warm", "pear")
    # And they can be cleared again.
    client.post("/profile", data={
        "suggest-undertone": "", "suggest-body_shape": "", "suggest-submit": "Save",
    })
    db.session.refresh(user)
    assert (user.undertone, user.body_shape) == (None, None)


def test_profile_rejects_unknown_values(client):
    register(client)
    client.post("/profile", data={"suggest-undertone": "green", "suggest-submit": "Save"})
    user = db.session.scalar(db.select(User).filter_by(username="alice"))
    assert user.undertone is None
