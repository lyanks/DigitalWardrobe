"""Admin: shared options (categories, colours, ...) and the dashboard."""
from app.extensions import db
from app.models import Category, GoalAnswer, Item, Option
from tests.conftest import logout, register
from tests.test_items import add_item, get_item


def admin(client):
    register(client, "boss", "boss@example.com")


def option(kind, value):
    return db.session.scalar(db.select(Option).filter_by(kind=kind, value=value))


def test_options_are_locked_too(client):
    register(client)
    assert client.get("/admin/options/color").status_code == 404
    assert client.post("/admin/options/color", data={"name": "teal"}).status_code == 404
    assert option("color", "teal") is None


def test_add_a_colour_and_use_it(client):
    admin(client)
    client.post("/admin/options/color", data={"name": " Teal ", "name_uk": "Бірюзовий",
                                              "hex": "#2a9d8f"})
    teal = option("color", "teal")
    assert teal.hex == "#2a9d8f"
    add_item(client, name="Teal top", color="teal")
    assert get_item("Teal top").color == "teal"
    # The Ukrainian name typed on the admin page is used in Ukrainian.
    client.post("/language/uk")
    assert "Бірюзовий" in client.get("/items/new").get_data(as_text=True)


def test_no_duplicates_and_safe_dot_colours(client):
    admin(client)
    page = client.post("/admin/options/color", data={"name": "Black", "hex": "#000000"}).get_data(as_text=True)
    assert "That one is already in the list." in page
    client.post("/admin/options/color", data={"name": "evil", "hex": "red;background:url(x)"})
    assert option("color", "evil") is None


def test_rename_changes_every_item(client):
    admin(client)
    add_item(client, name="Jeans", color="blue")
    blue = option("color", "blue")
    client.post(f"/admin/options/color/{blue.id}/edit", data={"name": "denim blue", "hex": "#3b6fd1"})
    assert get_item("Jeans").color == "denim blue"


def test_remove_unused_deletes_used_hides(client):
    admin(client)
    olive = option("color", "olive")
    client.post(f"/admin/options/color/{olive.id}/remove")
    assert option("color", "olive") is None

    add_item(client, name="Jeans", color="blue")
    blue = option("color", "blue")
    client.post(f"/admin/options/color/{blue.id}/remove")
    db.session.refresh(blue)
    assert blue.hidden
    # New items can't pick it, but the old one keeps it and can still be edited.
    page = client.get("/items/new").get_data(as_text=True)
    assert 'value="blue"' not in page
    item = get_item("Jeans")
    edit = client.get(f"/items/{item.id}/edit").get_data(as_text=True)
    assert 'value="blue"' in edit

    client.post(f"/admin/options/color/{blue.id}/show")
    db.session.refresh(blue)
    assert not blue.hidden


def test_all_seasons_is_built_in(client):
    admin(client)
    all_seasons = option("season", "all")
    assert client.post(f"/admin/options/season/{all_seasons.id}/remove").status_code == 404
    assert option("season", "all") is not None


def test_categories_add_rename_and_order(client):
    admin(client)
    client.post("/admin/options/category", data={"name": "Swimwear", "slot": "full",
                                                 "name_uk": "Купальники"})
    swim = db.session.scalar(db.select(Category).filter_by(name="Swimwear"))
    assert swim.slot == "full"
    client.post(f"/admin/options/category/{swim.id}/edit", data={"name": "Swimsuits", "slot": "full"})
    db.session.refresh(swim)
    assert swim.name == "Swimsuits"

    ids = [c.id for c in db.session.scalars(db.select(Category).order_by(Category.position))]
    new_order = [swim.id] + [i for i in ids if i != swim.id]
    assert client.post("/admin/options/category/order", json={"ids": new_order}).json == {"ok": True}
    first = db.session.scalar(db.select(Category).order_by(Category.position))
    assert first.name == "Swimsuits"
    # A list that doesn't match is refused.
    assert client.post("/admin/options/category/order", json={"ids": [1]}).status_code == 400


def test_last_visible_one_stays(client):
    admin(client)
    for row in db.session.scalars(db.select(Option).filter_by(kind="style")).all()[1:]:
        db.session.delete(row)
    db.session.commit()
    last = db.session.scalar(db.select(Option).filter_by(kind="style"))
    client.post(f"/admin/options/style/{last.id}/remove")
    assert option("style", last.value) is not None


def test_dashboard_numbers_and_goals(client):
    register(client, skip_setup=False)
    client.post("/welcome/2", data={"goals": ["plan", "track"]})
    add_item(client)
    logout(client)
    admin(client)
    page = client.get("/admin").get_data(as_text=True)
    assert '<span class="stat-number">2</span> users' in page
    assert '<span class="stat-number">1</span> item' in page
    assert "Plan outfits ahead" in page
    assert db.session.scalar(db.select(db.func.count()).select_from(GoalAnswer)) == 2
