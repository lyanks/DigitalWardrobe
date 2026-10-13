"""Idea #3: the wishlist. Wishes live in the item table with status="wishlist"."""
from datetime import date
from decimal import Decimal

from app.extensions import db
from app.filters import format_price, shop_name
from app.models import Item
from app.services.stats import wardrobe_stats
from tests.conftest import register
from tests.test_items import add_item, category_id, get_item


def add_wish(client, **fields):
    data = {
        "name": "Grey sport shorts", "category_id": category_id("Bottoms"),
        "color": "grey", "season": "summer", "style": "",
        "currency": "UAH", "priority": "0",
    }
    data.update(fields)
    return client.post("/items/wishlist/new", data=data,
                       content_type="multipart/form-data", follow_redirects=True)


def test_vague_wish_needs_only_name_category_color(client):
    register(client)
    page = add_wish(client).get_data(as_text=True)
    assert "Added “Grey sport shorts” to your wishlist." in page
    wish = get_item("Grey sport shorts")
    assert wish.status == "wishlist"
    assert wish.price is None and wish.shop_url is None and wish.priority is None


def test_wish_with_shop_link_price_and_priority(client):
    register(client)
    add_wish(client, name="Linen shirt", shop_url="https://www.example.com/shirt",
             price="1299.90", currency="UAH", priority="1")
    wish = get_item("Linen shirt")
    assert wish.price == Decimal("1299.90")
    assert wish.priority == 1
    page = client.get(f"/items/{wish.id}").get_data(as_text=True)
    assert "1 299.90 UAH" in page
    assert "example.com ↗" in page
    assert "Must have" in page
    assert "I bought it" in page


def test_bad_link_and_negative_price_are_refused(client):
    register(client)
    page = add_wish(client, shop_url="not a link", price="-5").get_data(as_text=True)
    assert "Paste a full link" in page
    assert "be negative" in page  # the apostrophe comes out as &#39; in HTML
    assert get_item("Grey sport shorts") is None


def test_wishes_stay_out_of_the_wardrobe_outfits_and_stats(client):
    register(client)
    add_item(client, name="Blue jeans")
    add_wish(client, name="Dream coat", category_id=category_id("Outerwear"))
    assert "Dream coat" not in client.get("/items").get_data(as_text=True)
    assert "Dream coat" not in client.get("/outfits/new").get_data(as_text=True)
    assert "Dream coat" not in client.get("/").get_data(as_text=True)
    assert wardrobe_stats(get_item("Blue jeans").user_id)["item_count"] == 1
    wishlist = client.get("/items/wishlist").get_data(as_text=True)
    assert "Dream coat" in wishlist and "Blue jeans" not in wishlist


def test_a_wish_cannot_go_into_an_outfit(client):
    register(client)
    add_item(client, name="Tee", category_id=category_id("Tops"))
    add_wish(client, name="Dream jeans")
    ids = [get_item("Tee").id, get_item("Dream jeans").id]
    response = client.post("/api/outfits/check", json={"item_ids": ids})
    assert response.status_code == 404


def test_i_bought_it_moves_the_wish_into_the_wardrobe(client):
    register(client)
    add_wish(client, name="Linen shirt", price="800", priority="2")
    wish = get_item("Linen shirt")
    page = client.post(f"/items/{wish.id}/bought", follow_redirects=True).get_data(as_text=True)
    assert "is in your wardrobe now" in page
    db.session.refresh(wish)
    assert wish.status == "owned"
    assert wish.purchase_date == date.today()
    assert wish.priority is None
    assert wish.price == Decimal("800")  # the price stays as a record
    assert "Linen shirt" in client.get("/items").get_data(as_text=True)


def test_owned_item_cannot_be_bought_again(client):
    register(client)
    add_item(client, name="Blue jeans")
    assert client.post(f"/items/{get_item('Blue jeans').id}/bought").status_code == 400


def test_wishlist_groups_by_priority(client):
    register(client)
    add_wish(client, name="Someday hat", priority="3")
    add_wish(client, name="Urgent boots", priority="1")
    add_wish(client, name="Whatever scarf")
    page = client.get("/items/wishlist").get_data(as_text=True)
    assert page.index("Urgent boots") < page.index("Someday hat") < page.index("Whatever scarf")
    assert "No priority" in page


def test_edit_form_fields_depend_on_the_kind(client):
    register(client)
    add_item(client, name="Blue jeans")
    add_wish(client, name="Dream coat")
    owned = client.get(f"/items/{get_item('Blue jeans').id}/edit").get_data(as_text=True)
    wish = client.get(f"/items/{get_item('Dream coat').id}/edit").get_data(as_text=True)
    assert "Bought on" in owned and "Link to the shop" not in owned
    assert "Link to the shop" in wish and "Bought on" not in wish


def test_price_and_shop_name_filters():
    assert format_price(Decimal("1299.90"), "UAH") == "1 299.90 UAH"
    assert format_price(Decimal("50.00"), "EUR") == "50 EUR"
    assert format_price(None) == ""
    assert shop_name("https://www.zara.com/ua/en/x.html") == "zara.com"
