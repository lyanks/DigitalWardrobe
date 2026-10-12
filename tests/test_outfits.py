import io
import os
from types import SimpleNamespace

from app.extensions import db
from app.models import Item, Outfit, OutfitItem
from app.services.outfit_rules import outfit_problems, sort_by_slot
from tests.conftest import logout, make_image, register
from tests.test_items import add_item, category_id, get_item


# ---------- the rules, without Flask or a database ----------

def fake(slot, name="x"):
    """Just enough of an Item for the rules: a name and a category slot."""
    return SimpleNamespace(name=name, category=SimpleNamespace(slot=slot))


def test_top_and_bottom_is_an_outfit():
    assert outfit_problems([fake("top"), fake("bottom")]) == []


def test_dress_alone_is_an_outfit():
    assert outfit_problems([fake("full"), fake("feet")]) == []


def test_empty_outfit_is_rejected():
    assert outfit_problems([]) == ["Pick at least one item."]


def test_top_without_bottom_is_rejected():
    problems = outfit_problems([fake("top"), fake("feet")])
    assert len(problems) == 1 and "a top and a bottom" in problems[0]


def test_two_tops_are_rejected_but_two_accessories_are_fine():
    assert outfit_problems([fake("top"), fake("top"), fake("bottom")]) == [
        "Only one top per outfit (you picked 2)."
    ]
    assert outfit_problems([fake("full"), fake("accessory"), fake("accessory")]) == []


def test_items_are_sorted_head_to_toe():
    items = [fake("feet", "boots"), fake("accessory", "hat"), fake("top", "shirt"), fake("outer", "coat")]
    assert [i.name for i in sort_by_slot(items)] == ["coat", "shirt", "boots", "hat"]


# ---------- helpers for the routes ----------

def make_basics(client):
    """A top, a bottom, shoes and a dress for the logged-in user."""
    add_item(client, name="White tee", category_id=category_id("Tops"), color="white")
    add_item(client, name="Blue jeans", category_id=category_id("Bottoms"), color="blue")
    add_item(client, name="Sneakers", category_id=category_id("Shoes"), color="white")
    add_item(client, name="Red dress", category_id=category_id("Dresses"), color="red")


def ids(*names):
    return [get_item(name).id for name in names]


def save_outfit(client, url="/outfits/new", **fields):
    data = {"name": "Weekend", "occasion": "casual", "notes": ""}
    data.update(fields)
    return client.post(url, data=data, content_type="multipart/form-data", follow_redirects=True)


def get_outfit(name):
    return db.session.scalar(db.select(Outfit).filter_by(name=name))


# ---------- access ----------

def test_outfits_require_login(client):
    response = client.get("/outfits")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_builder_asks_for_clothes_first(client):
    register(client)
    assert b"You need some clothes" in client.get("/outfits/new").data


# ---------- create ----------

def test_create_outfit(client):
    register(client)
    make_basics(client)
    response = save_outfit(client, item_ids=ids("Sneakers", "Blue jeans", "White tee"))

    assert "Saved the outfit “Weekend”".encode() in response.data
    outfit = get_outfit("Weekend")
    assert outfit.owner.username == "alice"
    assert outfit.occasion == "casual"
    # Stored head to toe, whatever order they were ticked in.
    assert [item.name for item in outfit.items] == ["White tee", "Blue jeans", "Sneakers"]
    assert [link.position for link in outfit.item_links] == [0, 1, 2]


def test_invalid_outfit_is_not_saved(client):
    register(client)
    make_basics(client)
    response = save_outfit(client, item_ids=ids("White tee", "Sneakers"))

    assert b"needs a top and a bottom" in response.data
    assert get_outfit("Weekend") is None
    # The ticked boxes stay ticked so you can fix it.
    assert response.data.count(b"checked") == 2


def test_outfit_needs_a_name(client):
    register(client)
    make_basics(client)
    response = save_outfit(client, name="", item_ids=ids("Red dress"))
    assert b"This field is required" in response.data
    assert db.session.query(Outfit).count() == 0


def test_cannot_use_someone_elses_item(client):
    register(client)
    make_basics(client)
    logout(client)
    register(client, username="bob", email="bob@example.com")
    add_item(client, name="Bob's jeans", category_id=category_id("Bottoms"))

    # Bob tries Alice's top with his jeans by sending her item's id.
    response = save_outfit(client, item_ids=ids("White tee", "Bob's jeans"))
    assert b"is not a valid choice" in response.data
    assert db.session.query(Outfit).count() == 0


# ---------- read ----------

def test_list_and_detail(client):
    register(client)
    make_basics(client)
    save_outfit(client, name="Date night", item_ids=ids("Red dress"))
    outfit = get_outfit("Date night")

    assert b"Date night" in client.get("/outfits").data
    page = client.get(f"/outfits/{outfit.id}").data
    assert b"Red dress" in page and b"incomplete" not in page


def test_other_users_outfit_is_404(client):
    register(client)
    make_basics(client)
    save_outfit(client, item_ids=ids("Red dress"))
    outfit_id = get_outfit("Weekend").id
    logout(client)
    register(client, username="bob", email="bob@example.com")

    for url in (f"/outfits/{outfit_id}", f"/outfits/{outfit_id}/edit", f"/outfits/{outfit_id}/delete"):
        assert client.get(url).status_code == 404
    assert client.post(f"/outfits/{outfit_id}/delete").status_code == 404
    assert get_outfit("Weekend") is not None


def test_item_page_lists_its_outfits(client):
    register(client)
    make_basics(client)
    save_outfit(client, name="Weekend", item_ids=ids("White tee", "Blue jeans"))
    save_outfit(client, name="Office", item_ids=ids("White tee", "Blue jeans", "Sneakers"))

    page = client.get(f"/items/{get_item('White tee').id}").data
    assert b"Appears in 2 outfits" in page
    assert b"Weekend" in page and b"Office" in page
    assert b"Appears in 0 outfits" in client.get(f"/items/{get_item('Red dress').id}").data


# ---------- update ----------

def test_edit_outfit_swaps_items(client):
    register(client)
    make_basics(client)
    save_outfit(client, item_ids=ids("White tee", "Blue jeans"))
    outfit = get_outfit("Weekend")

    # The edit page starts with the current items ticked.
    assert client.get(f"/outfits/{outfit.id}/edit").data.count(b"checked") == 2

    save_outfit(client, url=f"/outfits/{outfit.id}/edit", name="Party", occasion="party",
                item_ids=ids("Red dress", "Sneakers"))
    db.session.refresh(outfit)
    assert outfit.name == "Party"
    assert [item.name for item in outfit.items] == ["Red dress", "Sneakers"]
    # The old links are gone, not just hidden.
    assert db.session.query(OutfitItem).count() == 2


# ---------- delete ----------

def test_delete_outfit_keeps_the_items(client):
    register(client)
    make_basics(client)
    save_outfit(client, item_ids=ids("Red dress"))
    outfit_id = get_outfit("Weekend").id

    assert b"stay in your wardrobe" in client.get(f"/outfits/{outfit_id}/delete").data
    client.post(f"/outfits/{outfit_id}/delete", follow_redirects=True)
    assert get_outfit("Weekend") is None
    assert db.session.query(OutfitItem).count() == 0
    assert get_item("Red dress") is not None


def test_delete_item_keeps_the_outfit_but_flags_it(client):
    register(client)
    make_basics(client)
    save_outfit(client, item_ids=ids("White tee", "Blue jeans"))
    outfit = get_outfit("Weekend")
    tee_id = get_item("White tee").id

    assert b"taken out of 1 outfit" in client.get(f"/items/{tee_id}/delete").data
    client.post(f"/items/{tee_id}/delete", follow_redirects=True)

    db.session.expire_all()
    assert [item.name for item in get_outfit("Weekend").items] == ["Blue jeans"]
    assert b"incomplete" in client.get(f"/outfits/{outfit.id}").data


def test_deleting_user_deletes_their_outfits(app):
    from app.models import Category, User
    user = User(username="carol", email="carol@example.com")
    top = Item(owner=user, name="Top", color="black", category=db.session.scalar(db.select(Category).filter_by(slot="top")))
    outfit = Outfit(owner=user, name="Mono")
    outfit.item_links = [OutfitItem(item=top)]
    db.session.add(user)
    db.session.commit()

    db.session.delete(user)
    db.session.commit()
    assert db.session.query(Outfit).count() == 0
    assert db.session.query(OutfitItem).count() == 0


# ---------- outfit photo ----------

def test_outfit_photo_add_replace_remove(client, app):
    register(client)
    make_basics(client)
    save_outfit(client, item_ids=ids("Red dress"), photo=make_image("mirror.png", size=(800, 1600)))
    outfit = get_outfit("Weekend")
    first = outfit.image_path
    assert first.startswith("outfits/")
    folder = app.config["UPLOAD_FOLDER"]
    assert os.path.exists(os.path.join(folder, first))

    # The list and the detail page show it.
    assert first.encode() in client.get("/outfits").data
    assert first.encode() in client.get(f"/outfits/{outfit.id}").data

    # A new photo replaces the old file.
    save_outfit(client, url=f"/outfits/{outfit.id}/edit", item_ids=ids("Red dress"),
                photo=make_image("new.png"))
    db.session.refresh(outfit)
    assert outfit.image_path != first
    assert not os.path.exists(os.path.join(folder, first))

    # Ticking "remove" deletes it.
    second = outfit.image_path
    save_outfit(client, url=f"/outfits/{outfit.id}/edit", item_ids=ids("Red dress"), remove_photo="y")
    db.session.refresh(outfit)
    assert outfit.image_path is None
    assert not os.path.exists(os.path.join(folder, second))


def test_fake_outfit_photo_is_rejected(client):
    register(client)
    make_basics(client)
    response = save_outfit(client, item_ids=ids("Red dress"),
                           photo=(io.BytesIO(b"not an image"), "fake.png"))
    assert get_outfit("Weekend") is None
    assert b"field-error" in response.data


def test_deleting_outfit_deletes_its_photo(client, app):
    register(client)
    make_basics(client)
    save_outfit(client, item_ids=ids("Red dress"), photo=make_image())
    outfit = get_outfit("Weekend")
    path = os.path.join(app.config["UPLOAD_FOLDER"], outfit.image_path)

    assert b"The outfit and its photo are deleted" in client.get(f"/outfits/{outfit.id}/delete").data
    client.post(f"/outfits/{outfit.id}/delete")
    assert not os.path.exists(path)
