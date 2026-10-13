"""Laundry: put clothes "in the wash" and get reminded when you plan them."""
from datetime import timedelta
from types import SimpleNamespace

from app.services.laundry import wash_notice
from tests.conftest import register
from tests.test_items import get_item
from tests.test_outfits import make_basics
from tests.test_planner import TODAY, plan, setup_outfits
from tests.test_wishlist import add_wish


def fake(name, washing):
    return SimpleNamespace(name=name, in_wash=washing)


def wash(client, name, **data):
    return client.post(f"/items/{get_item(name).id}/laundry", data=data, follow_redirects=True)


def test_wash_notice_names_what_is_in_the_wash():
    assert wash_notice([fake("Tee", False)]) is None
    assert wash_notice([fake("Tee", True)]) == "Heads up: Tee is in the wash."
    items = [fake("Tee", True), fake("Jeans", True), fake("Socks", True), fake("Hat", False)]
    assert wash_notice(items) == "Heads up: Tee, Jeans and Socks are in the wash."


def test_put_in_the_wash_and_take_out(client):
    register(client)
    make_basics(client)
    page = wash(client, "White tee").get_data(as_text=True)
    assert "“White tee” is in the wash." in page and "In the wash since" in page
    assert get_item("White tee").washing_since == TODAY

    page = wash(client, "White tee").get_data(as_text=True)
    assert "“White tee” is clean again." in page
    assert get_item("White tee").washing_since is None


def test_goes_back_to_a_local_page_only(client):
    register(client)
    make_basics(client)
    item_id = get_item("White tee").id
    response = client.post(f"/items/{item_id}/laundry", data={"next": "/items"})
    assert response.headers["Location"].endswith("/items")
    response = client.post(f"/items/{item_id}/laundry", data={"next": "//evil.example"})
    assert response.headers["Location"].endswith(f"/items/{item_id}")


def test_wardrobe_filter(client):
    register(client)
    make_basics(client)
    wash(client, "White tee")
    in_wash = client.get("/items?wash=in").get_data(as_text=True)
    assert "White tee" in in_wash and "Blue jeans" not in in_wash
    clean = client.get("/items?wash=clean").get_data(as_text=True)
    assert "Blue jeans" in clean and "White tee" not in clean


def test_wishes_cannot_be_washed(client):
    register(client)
    add_wish(client)
    assert client.post(f"/items/{get_item('Grey sport shorts').id}/laundry").status_code == 400


def test_planning_clothes_in_the_wash_gives_a_heads_up(client):
    weekend, _ = setup_outfits(client)
    wash(client, "Blue jeans")
    page = plan(client, weekend, TODAY + timedelta(days=1)).get_data(as_text=True)
    assert "Heads up: Blue jeans is in the wash." in page

    data = client.post("/api/schedule", json={
        "outfit_id": weekend.id, "date": (TODAY + timedelta(days=2)).isoformat(),
    }).get_json()
    assert "Blue jeans is in the wash" in data["notice"]
