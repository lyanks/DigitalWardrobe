from datetime import date, timedelta

from app.extensions import db
from app.models import Item, ScheduledOutfit
from app.services.stats import breakdown, last_worn_dates, not_worn_lately, wardrobe_stats
from tests.conftest import logout, register
from tests.test_items import add_item, category_id, get_item
from tests.test_outfits import get_outfit, ids, make_basics, save_outfit
from tests.test_planner import entry_for, plan

TODAY = date.today()


def wear(client, outfit, day):
    """Plan an outfit on a day and mark it worn."""
    plan(client, outfit, day)
    client.post(f"/planner/{entry_for(outfit, day).id}/worn")


def alice_id():
    return get_item("White tee").user_id


# ---------- breakdown(), no database ----------

def test_breakdown_sorts_and_scales_to_the_biggest():
    rows = breakdown([("red", 1), ("black", 4), ("blue", 2)])
    assert [r["label"] for r in rows] == ["black", "blue", "red"]
    assert [r["percent"] for r in rows] == [100, 50, 25]
    assert breakdown([]) == []


# ---------- the queries ----------

def test_last_worn_dates_takes_the_latest_wear(client):
    register(client)
    make_basics(client)
    save_outfit(client, name="Weekend", item_ids=ids("White tee", "Blue jeans"))
    save_outfit(client, name="Date night", item_ids=ids("Red dress"))
    weekend = get_outfit("Weekend")
    wear(client, weekend, TODAY - timedelta(days=10))
    wear(client, weekend, TODAY - timedelta(days=2))
    plan(client, get_outfit("Date night"), TODAY)  # planned, not worn: doesn't count

    last = last_worn_dates(alice_id())
    assert last == {
        get_item("White tee").id: TODAY - timedelta(days=2),
        get_item("Blue jeans").id: TODAY - timedelta(days=2),
    }


def test_not_worn_lately(client):
    register(client)
    make_basics(client)
    save_outfit(client, name="Old", item_ids=ids("White tee", "Blue jeans"))
    save_outfit(client, name="Recent", item_ids=ids("Red dress"))
    wear(client, get_outfit("Old"), TODAY - timedelta(days=45))
    wear(client, get_outfit("Recent"), TODAY - timedelta(days=5))

    names = [item.name for item, _ in not_worn_lately(alice_id())]
    # Worn 45 days ago: stale. Worn 5 days ago: fine. Never worn: not here.
    assert sorted(names) == ["Blue jeans", "White tee"]
    assert len(not_worn_lately(alice_id(), limit=1)) == 1


def test_wardrobe_stats_numbers(client):
    register(client)
    make_basics(client)  # tee (white), jeans (blue), sneakers (white), dress (red)
    save_outfit(client, name="Weekend", item_ids=ids("White tee", "Blue jeans"))
    weekend = get_outfit("Weekend")
    wear(client, weekend, TODAY)
    wear(client, weekend, TODAY - timedelta(days=1))

    stats = wardrobe_stats(alice_id())
    assert stats["item_count"] == 4
    assert stats["total_wears"] == 4          # 2 items x 2 days
    assert stats["never_worn_count"] == 2
    assert [i.name for i in stats["most_worn"]] == ["Blue jeans", "White tee"]
    assert stats["least_worn"] == []          # only 2 worn items: nothing to compare
    assert stats["by_color"][0] == {"label": "white", "count": 2, "percent": 100, "swatch": "#f7f7f5"}
    assert {r["label"]: r["count"] for r in stats["by_category"]} == {
        "Tops": 1, "Bottoms": 1, "Shoes": 1, "Dresses": 1,
    }


def test_stats_only_count_your_own_things(client):
    register(client)
    make_basics(client)
    logout(client)
    register(client, username="bob", email="bob@example.com")
    add_item(client, name="Bob's hat", category_id=category_id("Accessories"))
    bob = get_item("Bob's hat").user_id

    stats = wardrobe_stats(bob)
    assert stats["item_count"] == 1
    assert [r["label"] for r in stats["by_category"]] == ["Accessories"]


# ---------- the pages ----------

def test_stats_page(client):
    register(client)
    assert b"Add some clothes first" in client.get("/stats").data

    make_basics(client)
    save_outfit(client, name="Weekend", item_ids=ids("White tee", "Blue jeans"))
    wear(client, get_outfit("Weekend"), TODAY)
    page = client.get("/stats").data.decode()
    assert "Most worn" in page and "White tee" in page
    assert "Never worn: 2 items" in page
    assert "--width: 100%" in page  # the biggest bar fills the track


def test_stats_requires_login(client):
    assert client.get("/stats").status_code == 302


def test_item_page_shows_last_worn(client):
    register(client)
    make_basics(client)
    save_outfit(client, name="Weekend", item_ids=ids("White tee", "Blue jeans"))
    day = TODAY - timedelta(days=3)
    wear(client, get_outfit("Weekend"), day)
    page = client.get(f"/items/{get_item('White tee').id}").data.decode()
    assert f"last {day.strftime('%d.%m.%Y')}" in page
    assert "last " not in client.get(f"/items/{get_item('Red dress').id}").data.decode().split("Worn")[1][:80]


def test_home_suggests_clothes_not_worn_lately(client):
    register(client)
    make_basics(client)
    save_outfit(client, name="Weekend", item_ids=ids("White tee", "Blue jeans"))
    assert b"Not worn lately" not in client.get("/").data

    wear(client, get_outfit("Weekend"), TODAY - timedelta(days=40))
    page = client.get("/").data.decode()
    assert "Not worn lately" in page
    assert "White tee" in page.split("Not worn lately")[1].split("Recently added")[0]
