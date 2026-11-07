"""Several seasons/styles/moods per item, the cut-out preview and AI details."""
import io

import pytest
from PIL import Image

from app import options
from app.extensions import db
from app.models import Category, Item, Outfit, OutfitItem
from app.services import ai, autotag
from tests.conftest import make_image, register


def category_id(name):
    return db.session.scalar(db.select(Category.id).filter_by(name=name))


def add_item(client, **fields):
    data = {"name": "Coat", "category_id": category_id("Outerwear"), "color": "black"}
    data.update(fields)
    return client.post("/items/new", data=data, content_type="multipart/form-data",
                       follow_redirects=True)


def get_item(name):
    return db.session.scalar(db.select(Item).filter_by(name=name))


# ---------- chips ----------

def test_form_shows_chips_and_no_all_season_chip(client):
    register(client)
    page = client.get("/items/new").data.decode()
    assert 'name="seasons" value="winter"' in page
    assert 'name="moods" value="comfortable"' in page
    assert 'name="seasons" value="all"' not in page  # nothing picked = all year


def test_every_season_ticked_means_all_year(client):
    register(client)
    add_item(client, seasons=["spring", "summer", "autumn", "winter"])
    assert get_item("Coat").seasons == []


def test_edit_form_ticks_saved_chips(client):
    register(client)
    add_item(client, seasons=["winter"], moods=["classy"])
    item = get_item("Coat")
    page = client.get(f"/items/{item.id}/edit").data.decode()
    assert 'value="winter"\n                 checked' in page
    detail = client.get(f"/items/{item.id}").data.decode()
    assert "Winter" in detail and "Classy" in detail


def test_unknown_chip_value_is_refused(client):
    register(client)
    page = add_item(client, moods=["sparkly"]).data
    assert get_item("Coat") is None
    assert b"field-error" in page


def test_rename_and_count_a_mood(client, app):
    register(client)
    add_item(client, name="Coat", moods=["classy", "elegant"])
    add_item(client, name="Robe", moods=["home"])
    assert options.uses("mood", "classy") == 1
    options.rename("mood", "classy", "elegant")  # the coat already has "elegant"
    db.session.commit()
    assert get_item("Coat").moods == ["elegant"]


def test_outfit_mood_is_what_all_items_share(app):
    def item(moods):
        it = Item(user_id=1, category_id=1, name="x", color="black")
        it.set_tags("mood", moods)
        return it
    outfit = Outfit(user_id=1, name="Evening")
    outfit.item_links = [OutfitItem(item=item(["classy", "elegant"])),
                         OutfitItem(item=item(["elegant"])),
                         OutfitItem(item=item([]))]  # no mood: doesn't count
    assert outfit.moods == ["elegant"]


def test_admin_lists_moods(client, app):
    register(client, username="boss", email="boss@example.com")
    page = client.get("/admin/options/mood")
    assert page.status_code == 200 and b"comfortable" in page.data


# ---------- cut-out preview ----------

def shirt_on_white():
    image = Image.new("RGB", (300, 300), "white")
    for x in range(100, 200):
        for y in range(80, 220):
            image.putpixel((x, y), (30, 60, 160))
    out = io.BytesIO()
    image.save(out, "JPEG")
    out.seek(0)
    return out


def test_cutout_preview_returns_see_through_png(client):
    register(client)
    response = client.post("/api/photos/cutout", data={"photo": (shirt_on_white(), "shirt.jpg")},
                           content_type="multipart/form-data")
    assert response.status_code == 200 and response.mimetype == "image/png"
    cut = Image.open(io.BytesIO(response.data))
    assert cut.mode == "RGBA"
    assert cut.getpixel((5, 5))[3] == 0          # background gone
    assert cut.getpixel((150, 150))[3] == 255    # shirt kept


def test_cutout_preview_refuses_a_busy_background(client):
    register(client)
    noisy = Image.effect_noise((200, 200), 120).convert("RGB")
    out = io.BytesIO()
    noisy.save(out, "PNG")
    out.seek(0)
    response = client.post("/api/photos/cutout", data={"photo": (out, "busy.png")},
                           content_type="multipart/form-data")
    assert response.status_code == 422
    assert "busy" in response.get_json()["error"]


def test_saving_an_edited_png_keeps_it_see_through(client, app):
    register(client)
    image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    image.paste((200, 20, 20, 255), (20, 20, 80, 80))
    out = io.BytesIO()
    image.save(out, "PNG")
    out.seek(0)
    add_item(client, photo=(out, "photo.png"))
    assert get_item("Coat").image_path.endswith(".png")


# ---------- AI details ----------

@pytest.fixture
def fake_claude(monkeypatch):
    """Answer like Claude would, without the internet. Keeps what was asked."""
    asked = {}

    def fake(prompt, schema, image_bytes=None, **kwargs):
        asked.update(prompt=prompt, schema=schema, image=image_bytes)
        return {"name": "Black leather bomber jacket", "category": "Outerwear",
                "color": "black", "seasons": ["autumn", "winter"],
                "styles": ["streetwear"], "moods": ["classy"], "brand": ""}

    monkeypatch.setattr(autotag, "ask_claude", fake)
    return asked


def post_photo(client):
    return client.post("/api/photos/details", data={"photo": make_image("jacket.png")},
                       content_type="multipart/form-data")


def test_details_from_photo(client, fake_claude):
    register(client)
    response = post_photo(client)
    assert response.status_code == 200
    answer = response.get_json()
    assert answer["category_id"] == category_id("Outerwear")
    assert answer["moods"] == ["classy"]
    # The model may only pick from our own lists.
    properties = fake_claude["schema"]["properties"]
    assert "comfortable" in properties["moods"]["items"]["enum"]
    assert "all" not in properties["seasons"]["items"]["enum"]
    # It got a small JPEG, not the original upload.
    assert Image.open(io.BytesIO(fake_claude["image"])).format == "JPEG"


def test_details_have_a_daily_limit(client, app, fake_claude):
    register(client)
    app.config["AI_DAILY_LIMIT"] = 2
    assert post_photo(client).status_code == 200
    assert post_photo(client).status_code == 200
    response = post_photo(client)
    assert response.status_code == 429
    assert "tomorrow" in response.get_json()["error"]


def test_details_off_without_a_key(client, app, fake_claude):
    register(client)
    app.config["ANTHROPIC_API_KEY"] = ""
    assert post_photo(client).status_code == 503
    assert b"data-details-url" not in client.get("/items/new").data


def test_ai_errors_become_friendly_messages(client, monkeypatch):
    register(client)

    def broken(*args, **kwargs):
        raise ai.AiError("Couldn't reach the AI. Try again.")

    monkeypatch.setattr(autotag, "ask_claude", broken)
    response = post_photo(client)
    assert response.status_code == 503
    assert response.get_json()["error"] == "Couldn't reach the AI. Try again."


def test_ask_claude_sends_image_and_schema(app, monkeypatch):
    """The real ask_claude, with a fake SDK client: checks what we send."""
    sent = {}

    class FakeMessages:
        def create(self, **kwargs):
            sent.update(kwargs)

            class Block:
                type = "text"
                text = '{"ok": true}'

            class Response:
                stop_reason = "end_turn"
                content = [Block()]
            return Response()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(ai, "_client", lambda: FakeClient())
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}},
              "required": ["ok"], "additionalProperties": False}
    assert ai.ask_claude("hi", schema, image_bytes=b"abc") == {"ok": True}
    assert sent["model"] == "claude-haiku-5-5"
    assert sent["output_config"]["format"]["schema"] == schema
    image = sent["messages"][0]["content"][0]
    assert image["type"] == "image" and image["source"]["data"] == "YWJj"
