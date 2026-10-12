import io
import os
from datetime import date

from app.extensions import db
from app.models import Category, Item
from tests.conftest import logout, make_image, register


def category_id(name):
    return db.session.scalar(db.select(Category.id).filter_by(name=name))


def add_item(client, **fields):
    data = {
        "name": "Blue jeans", "category_id": category_id("Bottoms"),
        "color": "blue", "season": "all", "style": "",
    }
    data.update(fields)
    return client.post("/items/new", data=data,
                       content_type="multipart/form-data", follow_redirects=True)


def get_item(name):
    return db.session.scalar(db.select(Item).filter_by(name=name))


# ---------- access ----------

def test_wardrobe_requires_login(client):
    response = client.get("/items")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_seed_creates_six_categories(app):
    assert db.session.query(Category).count() == 6


# ---------- create ----------

def test_add_item_with_all_fields_and_photo(client, app):
    register(client)
    response = add_item(
        client, name="Linen shirt", category_id=category_id("Tops"), color="white",
        season="summer", style="casual", brand="Uniqlo", size="M",
        purchase_date="2026-05-01", notes="Wash cold",
        photo=make_image("IMG_1234.png", size=(3000, 2000)),
    )

    assert "Added “Linen shirt”".encode() in response.data
    item = get_item("Linen shirt")
    assert item.owner.username == "alice"
    assert item.category.slot == "top"
    assert (item.color, item.season, item.style) == ("white", "summer", "casual")
    assert item.purchase_date == date(2026, 5, 1)
    assert item.times_worn == 0

    # The photo got a random name and was shrunk to at most 1200 px.
    assert item.image_path.startswith("items/") and "IMG_1234" not in item.image_path
    from PIL import Image
    with Image.open(os.path.join(app.config["UPLOAD_FOLDER"], item.image_path)) as saved:
        assert max(saved.size) == 1200


def test_add_item_requires_a_name(client):
    register(client)
    response = add_item(client, name="")
    assert b"This field is required." in response.data
    assert db.session.query(Item).count() == 0


def test_add_item_rejects_unknown_color_and_category(client):
    register(client)
    response = add_item(client, color="sparkly", category_id=999)
    assert b"Not a valid choice" in response.data
    assert db.session.query(Item).count() == 0


def test_add_item_rejects_fake_photo(client):
    register(client)
    response = add_item(client, photo=(io.BytesIO(b"definitely not a jpeg"), "x.jpg"))
    assert b"not a readable image" in response.data
    assert db.session.query(Item).count() == 0


# ---------- read ----------

def test_list_and_detail(client):
    register(client)
    add_item(client, name="Blue jeans")
    add_item(client, name="Black boots", category_id=category_id("Shoes"), color="black")

    page = client.get("/items").data
    assert b"Blue jeans" in page and b"Black boots" in page
    assert b"Showing 2 of 2" in page

    item = get_item("Black boots")
    page = client.get(f"/items/{item.id}").data
    assert b"Shoes" in page and b"Worn" in page


def test_filters(client):
    register(client)
    add_item(client, name="Blue jeans", season="all")
    add_item(client, name="Wool coat", category_id=category_id("Outerwear"),
             color="grey", season="winter", brand="Zara")
    add_item(client, name="Shorts", color="beige", season="summer")

    def names(query):
        page = client.get("/items" + query).data.decode()
        return {n for n in ("Blue jeans", "Wool coat", "Shorts") if n in page}

    assert names("?color=grey") == {"Wool coat"}
    assert names(f"?category={category_id('Bottoms')}") == {"Blue jeans", "Shorts"}
    # "all season" items also match a season filter.
    assert names("?season=winter") == {"Blue jeans", "Wool coat"}
    assert names("?q=zara") == {"Wool coat"}  # brand, case-insensitive
    assert names("?q=JEANS&color=blue") == {"Blue jeans"}
    assert names("?color=sparkly") == {"Blue jeans", "Wool coat", "Shorts"}  # ignored


def test_home_shows_recent_items(client):
    register(client)
    add_item(client, name="Blue jeans")
    page = client.get("/").data
    assert b"1 item in your wardrobe" in page
    assert b"Blue jeans" in page


# ---------- update ----------

def test_edit_item(client):
    register(client)
    add_item(client, name="Blue jeans", photo=make_image())
    item = get_item("Blue jeans")
    old_photo = item.image_path

    form_page = client.get(f"/items/{item.id}/edit").data
    assert b'value="Blue jeans"' in form_page  # pre-filled

    response = client.post(f"/items/{item.id}/edit", data={
        "name": "Dark jeans", "category_id": item.category_id, "color": "navy",
        "season": "autumn", "style": "", "remove_photo": "y",
    }, follow_redirects=True)

    assert b"Changes saved." in response.data
    db.session.refresh(item)
    assert (item.name, item.color, item.season) == ("Dark jeans", "navy", "autumn")
    assert item.image_path is None
    assert client.get(f"/uploads/{old_photo}").status_code == 404  # file deleted


# ---------- delete ----------

def test_delete_asks_first_then_deletes(client):
    register(client)
    add_item(client, name="Old hoodie", photo=make_image())
    item = get_item("Old hoodie")
    item_id, photo = item.id, item.image_path

    # GET only shows the question.
    page = client.get(f"/items/{item_id}/delete").data
    assert "Delete “Old hoodie”?".encode() in page
    assert db.session.get(Item, item_id) is not None

    response = client.post(f"/items/{item_id}/delete", follow_redirects=True)
    assert "Deleted “Old hoodie”".encode() in response.data
    assert db.session.get(Item, item_id) is None
    assert client.get(f"/uploads/{photo}").status_code == 404


# ---------- ownership ----------

def test_users_only_see_their_own_items(client):
    register(client, "alice", "alice@example.com")
    add_item(client, name="Alice's scarf", category_id=category_id("Accessories"))
    scarf = get_item("Alice's scarf")
    logout(client)

    register(client, "bob", "bob@example.com")
    assert b"Alice&#39;s scarf" not in client.get("/items").data  # apostrophe is HTML-escaped

    # Every route for a single item answers 404 for someone else's item.
    assert client.get(f"/items/{scarf.id}").status_code == 404
    assert client.get(f"/items/{scarf.id}/edit").status_code == 404
    assert client.post(f"/items/{scarf.id}/edit", data={"name": "Mine now"}).status_code == 404
    assert client.get(f"/items/{scarf.id}/delete").status_code == 404
    assert client.post(f"/items/{scarf.id}/delete").status_code == 404

    db.session.refresh(scarf)
    assert scarf.name == "Alice's scarf"


def test_missing_item_is_404(client):
    register(client)
    assert client.get("/items/12345").status_code == 404
