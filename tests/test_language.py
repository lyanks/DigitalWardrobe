"""English and Ukrainian: the switch, who remembers what, and translated pages."""
from datetime import date

import pytest
from flask_babel import force_locale, refresh

from app.extensions import db
from app.i18n import js_texts, month_year, weekday
from app.models import User
from tests.conftest import register
from tests.test_items import add_item, category_id, get_item

UA = {"Accept-Language": "uk-UA,uk;q=0.9,en;q=0.5"}


@pytest.fixture(autouse=True)
def fresh_language(app):
    """Flask-Babel remembers the language for the whole app context. A real
    server gets a new one per request; the tests share one, so forget the
    language before every request, like the server does."""
    app.before_request(refresh)


def alice():
    return db.session.scalar(db.select(User).filter_by(username="alice"))


def test_english_by_default(client):
    page = client.get("/").get_data(as_text=True)
    assert '<html lang="en"' in page and "Get started free" in page


def test_a_ukrainian_browser_gets_ukrainian(client):
    page = client.get("/", headers=UA).get_data(as_text=True)
    assert '<html lang="uk"' in page and "Почати безкоштовно" in page


def test_the_switch_wins_over_the_browser_and_returns_to_the_page(client):
    response = client.post("/language/uk", data={"next": "/tutorial"})
    assert response.headers["Location"].endswith("/tutorial")
    assert "Як це працює" in client.get("/tutorial").get_data(as_text=True)
    client.post("/language/en")
    assert "How it works" in client.get("/tutorial", headers=UA).get_data(as_text=True)


def test_unknown_language_and_outside_links(client):
    assert client.post("/language/de").status_code == 404
    response = client.post("/language/uk", data={"next": "//evil.example"})
    assert response.headers["Location"].endswith("/")


def test_a_users_choice_is_saved_on_the_account(client):
    register(client)
    client.post("/language/uk")
    assert alice().language == "uk"
    add_item(client, name="White tee", category_id=category_id("Tops"), color="light blue")
    page = client.get(f"/items/{get_item('White tee').id}").get_data(as_text=True)
    assert "Верх" in page and "Блакитний" in page.replace("блакитний", "Блакитний")


def test_dates_and_script_texts_follow_the_language(app):
    wednesday = date(2026, 10, 14)
    with app.test_request_context(), force_locale("uk"):
        assert weekday(wednesday) == "середа"
        assert month_year(wednesday) == "Жовтень 2026"
        assert js_texts()["Saving…"] == "Зберігаю…"
    with app.test_request_context(), force_locale("en"):
        assert weekday(wednesday) == "Wednesday"
        assert js_texts()["Saving…"] == "Saving…"


def test_every_ukrainian_text_is_translated(app):
    """The .po file has no empty translations (pybabel would show English)."""
    import os
    from babel.messages.pofile import read_po
    path = os.path.join(app.root_path, "translations", "uk", "LC_MESSAGES", "messages.po")
    with open(path, "rb") as f:
        catalog = read_po(f)
    empty = [m.id for m in catalog if m.id and not all(m.string if m.pluralizable else [m.string])]
    assert empty == []
