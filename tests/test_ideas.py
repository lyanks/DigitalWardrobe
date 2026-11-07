"""Ideas: saved pins and pictures, and outfits that recreate them."""
import io

import pytest
from PIL import Image

from app.extensions import db
from app.models import Idea, User
from app.services import pins
from app.services.product_page import FetchError
from tests.conftest import logout, make_image, register
from tests.test_outfits import get_outfit, ids, make_basics, save_outfit

PIN_PAGE = """<html><head>
<meta property="og:title" content="Camel coat and jeans">
<meta property="og:image" content="https://i.pinimg.com/736x/ab/cd/coat.jpg">
</head><body>a pin</body></html>"""


def png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (30, 40), "orange").save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def pinterest(monkeypatch):
    """A fake Pinterest: the pin page and its picture, without the internet.
    Set pinterest.picture_works = False to act like a blocked picture site."""
    state = type("Fake", (), {"picture_works": True, "asked": []})()

    def fake_download(url, max_bytes):
        state.asked.append(url)
        return PIN_PAGE.encode(), "text/html; charset=utf-8"

    def fake_download_image(url):
        if not state.picture_works:
            raise FetchError("blocked")
        return png_bytes()

    monkeypatch.setattr(pins, "download", fake_download)
    monkeypatch.setattr("app.ideas.routes.download_image", fake_download_image)
    return state


# ---------- reading a pin page ----------

def test_read_pin_finds_picture_and_title():
    found = pins.read_pin(PIN_PAGE, "https://www.pinterest.com/pin/1/")
    assert found == {"title": "Camel coat and jeans", "image_url": "https://i.pinimg.com/736x/ab/cd/coat.jpg"}


def test_read_pin_makes_relative_links_full_and_refuses_odd_ones():
    page = '<meta property="og:image" content="/img/a.jpg"><title> A page </title>'
    assert pins.read_pin(page, "https://blog.example/post") == {"title": "A page", "image_url": "https://blog.example/img/a.jpg"}
    assert pins.read_pin('<meta property="og:image" content="javascript:alert(1)">', "https://x.example/")["image_url"] is None


def test_a_page_without_a_picture_is_an_error(monkeypatch):
    monkeypatch.setattr(pins, "download", lambda url, size: (b"<html>no picture</html>", "text/html"))
    with pytest.raises(FetchError, match="Couldn't find a picture"):
        pins.fetch_pin("https://www.pinterest.com/pin/1/")


# ---------- the ideas page ----------

def test_ideas_need_login(client):
    assert client.get("/ideas").status_code == 302


def test_save_a_pin_link(client, app, pinterest):
    register(client)
    page = client.post("/ideas", data={"link": "https://pin.it/abc", "note": "for autumn"},
                       follow_redirects=True).get_data(as_text=True)
    assert "Idea saved." in page and "Camel coat and jeans" in page and "for autumn" in page
    idea = db.session.scalar(db.select(Idea))
    assert idea.source_url == "https://pin.it/abc"
    assert idea.image_path.startswith("ideas/")  # our own copy of the picture


def test_a_blocked_picture_is_shown_from_the_web(client, pinterest):
    register(client)
    pinterest.picture_works = False
    page = client.post("/ideas", data={"link": "https://pin.it/abc"}, follow_redirects=True).get_data(as_text=True)
    idea = db.session.scalar(db.select(Idea))
    assert idea.image_path is None
    assert 'src="https://i.pinimg.com/736x/ab/cd/coat.jpg"' in page and 'referrerpolicy="no-referrer"' in page


def test_upload_a_picture_instead(client):
    register(client)
    client.post("/ideas", data={"photo": make_image(), "note": "screenshot"},
                content_type="multipart/form-data", follow_redirects=True)
    idea = db.session.scalar(db.select(Idea))
    assert idea.image_path and idea.source_url is None and idea.note == "screenshot"


def test_a_link_or_a_picture_is_needed(client):
    register(client)
    page = client.post("/ideas", data={"note": "nothing"}).get_data(as_text=True)
    assert "Paste a pin link or choose a picture." in page
    assert db.session.scalar(db.select(Idea)) is None


def test_a_bad_link_shows_the_reason(client):
    register(client)
    page = client.post("/ideas", data={"link": "http://127.0.0.1/pin"}).get_data(as_text=True)
    assert "public website" in page


def test_delete_an_idea_keeps_the_outfit(client, app, pinterest):
    register(client)
    make_basics(client)
    client.post("/ideas", data={"link": "https://pin.it/abc"})
    idea = db.session.scalar(db.select(Idea))
    save_outfit(client, item_ids=ids("White tee", "Blue jeans"), idea_id=idea.id)
    assert get_outfit("Weekend").idea_id == idea.id

    client.post(f"/ideas/{idea.id}/delete", follow_redirects=True)
    db.session.expire_all()
    assert db.session.scalar(db.select(Idea)) is None
    assert get_outfit("Weekend").idea_id is None


def test_other_peoples_ideas_are_off_limits(client, pinterest):
    register(client)
    make_basics(client)
    client.post("/ideas", data={"link": "https://pin.it/abc"})
    idea_id = db.session.scalar(db.select(Idea)).id
    logout(client)
    register(client, username="bob", email="bob@example.com")
    make_basics(client)
    assert client.post(f"/ideas/{idea_id}/delete").status_code == 404
    bob = db.session.scalar(db.select(User).filter_by(username="bob"))
    bobs = {item.name: item.id for item in bob.items}
    save_outfit(client, item_ids=[bobs["White tee"], bobs["Blue jeans"]], idea_id=idea_id)
    assert get_outfit("Weekend").idea_id is None  # not bob's idea: ignored


# ---------- inspiration on outfits ----------

def test_outfit_page_shows_its_inspiration(client, pinterest):
    register(client)
    make_basics(client)
    client.post("/ideas", data={"link": "https://www.pinterest.com/pin/123/"})
    idea = db.session.scalar(db.select(Idea))
    form = client.get("/outfits/new").get_data(as_text=True)
    assert 'name="idea_id" value="0" checked' in form and f'value="{idea.id}"' in form
    save_outfit(client, item_ids=ids("White tee", "Blue jeans"), idea_id=idea.id)
    page = client.get(f"/outfits/{get_outfit('Weekend').id}").get_data(as_text=True)
    assert "Inspired by this pin" in page and 'href="https://www.pinterest.com/pin/123/"' in page
