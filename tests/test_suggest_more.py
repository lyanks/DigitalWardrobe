"""Weather, "Wear it" / "Not for me", AI from a pin, data export and the phone app."""
import io
import json
import zipfile

import pytest

from app.extensions import db
from app.models import Idea, Outfit, SuggestionVote, User, WearLog
from app.services import ai
from tests.conftest import logout, register
from tests.test_outfits import get_outfit, ids, make_basics


def votes():
    return db.session.scalars(db.select(SuggestionVote).order_by(SuggestionVote.id)).all()


def look_ids(*names):
    return ",".join(map(str, ids(*names)))


# ---------- weather ----------

def test_weather_line_and_bad_numbers(client):
    register(client)
    make_basics(client)
    page = client.get("/outfits/suggest?season=summer&temp=8.6&rain=70").get_data(as_text=True)
    assert "Today feels like 9 °C, 70% chance of rain." in page
    page = client.get("/outfits/suggest?temp=hot&rain=500").get_data(as_text=True)
    assert "Use today&#39;s weather" in page or "Use today's weather" in page


# ---------- learning ----------

def test_not_for_me_saves_a_vote_and_goes_back(client):
    register(client)
    make_basics(client)
    response = client.post("/outfits/suggest/skip", data={
        "item_ids": look_ids("White tee", "Blue jeans"), "back": "/outfits/suggest?season=summer",
    })
    assert response.headers["Location"].endswith("/outfits/suggest?season=summer")
    [vote] = votes()
    assert not vote.liked and vote.id_set == set(ids("White tee", "Blue jeans"))


def test_back_never_leaves_the_site(client):
    register(client)
    make_basics(client)
    response = client.post("/outfits/suggest/skip", data={
        "item_ids": look_ids("White tee"), "back": "https://evil.example.com/",
    })
    assert response.headers["Location"].endswith("/outfits/suggest")


def test_wear_it_logs_today_and_likes(client):
    register(client)
    make_basics(client)
    client.post("/outfits/suggest/wear", data={"item_ids": look_ids("White tee", "Blue jeans", "Sneakers")})
    [log] = db.session.scalars(db.select(WearLog)).all()
    assert {item.name for item in log.items} == {"White tee", "Blue jeans", "Sneakers"}
    assert votes()[0].liked


def test_wear_it_refuses_a_broken_look(client):
    register(client)
    make_basics(client)
    client.post("/outfits/suggest/wear", data={"item_ids": look_ids("Sneakers")})
    assert db.session.scalars(db.select(WearLog)).all() == []


def test_votes_are_only_about_my_clothes(client):
    register(client)
    make_basics(client)
    alice = look_ids("White tee", "Blue jeans")
    logout(client)
    register(client, username="bob", email="bob@example.com")
    client.post("/outfits/suggest/skip", data={"item_ids": alice})
    assert votes() == []


def test_saving_counts_as_liked(client):
    register(client)
    make_basics(client)
    client.post("/outfits/suggest/save", data={"name": "Mine", "item_ids": look_ids("Red dress", "Sneakers")})
    assert votes()[0].liked


# ---------- AI from a pin ----------

@pytest.fixture
def idea(client):
    register(client)
    make_basics(client)
    user = db.session.scalar(db.select(User).filter_by(username="alice"))
    idea = Idea(user_id=user.id, title="Red dress look", image_url="https://i.pinimg.com/736x/x.jpg")
    db.session.add(idea)
    db.session.commit()
    return idea


def test_pin_button_and_suggestion(client, idea, monkeypatch):
    asked = {}

    def fake(idea_arg, items, language):
        asked["ids"] = [item.id for item in items]
        return {"item_ids": ids("Red dress", "Sneakers") + [99999], "missing": ["belt"],
                "note": "A red dress with white sneakers."}

    monkeypatch.setattr("app.ideas.routes.match_pin", fake)
    assert "Make it with my clothes" in client.get("/ideas").get_data(as_text=True)
    page = client.post(f"/ideas/{idea.id}/suggest").get_data(as_text=True)
    assert "A red dress with white sneakers." in page
    assert "belt" in page and "Save as outfit" in page
    # Saving keeps the pin as the outfit's inspiration.
    client.post("/outfits/suggest/save", data={
        "name": "Pin look", "item_ids": look_ids("Red dress", "Sneakers"), "idea_id": str(idea.id),
    })
    assert get_outfit("Pin look").idea_id == idea.id


def test_pin_suggestion_is_private(client, idea):
    logout(client)
    register(client, username="bob", email="bob@example.com")
    assert client.post(f"/ideas/{idea.id}/suggest").status_code == 404


def test_pin_suggestion_counts_towards_the_daily_limit(client, idea, app, monkeypatch):
    app.config["AI_DAILY_LIMIT"] = 0
    monkeypatch.setattr("app.ideas.routes.match_pin", lambda *a: pytest.fail("should not call"))
    page = client.post(f"/ideas/{idea.id}/suggest", follow_redirects=True).get_data(as_text=True)
    assert "That's all the AI help for today" in page or "That&#39;s all the AI help" in page


def test_pin_picture_is_sent_by_url(client, idea, monkeypatch):
    """No copy on our server: Claude gets the pin's web address."""
    sent = {}

    class FakeMessages:
        def create(self, **kwargs):
            sent.update(kwargs)
            text = json.dumps({"item_ids": [], "missing": [], "note": "ok"})
            block = type("B", (), {"type": "text", "text": text})()
            return type("R", (), {"stop_reason": "end_turn", "content": [block]})()

    monkeypatch.setattr(ai, "_client", lambda: type("C", (), {"messages": FakeMessages()})())
    client.post(f"/ideas/{idea.id}/suggest")
    image = sent["messages"][0]["content"][0]
    assert image["source"] == {"type": "url", "url": "https://i.pinimg.com/736x/x.jpg"}
    enum = sent["output_config"]["format"]["schema"]["properties"]["item_ids"]["items"]["enum"]
    assert set(enum) == set(ids("White tee", "Blue jeans", "Sneakers", "Red dress"))


def test_no_key_no_pin_button(client, idea, app):
    app.config["ANTHROPIC_API_KEY"] = ""
    assert "Make it with my clothes" not in client.get("/ideas").get_data(as_text=True)


# ---------- download my data ----------

def test_download_my_data(client):
    register(client)
    make_basics(client)
    response = client.get("/profile/export")
    assert response.mimetype == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(response.data))
    data = json.loads(archive.read("data.json"))
    assert data["profile"]["username"] == "alice"
    assert {item["name"] for item in data["items"]} == {"White tee", "Blue jeans", "Sneakers", "Red dress"}


def test_export_needs_login(client):
    assert client.get("/profile/export").status_code == 302


# ---------- install as an app ----------

def test_pwa_files(client):
    page = client.get("/login").get_data(as_text=True)
    assert "manifest.webmanifest" in page
    response = client.get("/sw.js")
    assert response.status_code == 200 and "javascript" in response.mimetype
    manifest = json.loads(client.get("/static/manifest.webmanifest").data)
    assert manifest["display"] == "standalone"
    assert client.get("/static/offline.html").status_code == 200
