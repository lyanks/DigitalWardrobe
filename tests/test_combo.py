"""Idea #1: the wear log and the "You wore this combo recently" check."""
from datetime import date, timedelta
from types import SimpleNamespace

from app.extensions import db
from app.models import WearLog
from app.services.combo_check import combo_ids, combo_notice, matching_days
from app.services.stats import last_worn_date
from tests.conftest import logout, register
from tests.test_items import get_item
from tests.test_outfits import get_outfit, ids, make_basics, save_outfit
from tests.test_planner import TODAY, entry_for, plan, setup_outfits

WED = date(2026, 10, 7)


def fake(item_id, slot, name=None):
    """Just enough of an Item for the pure functions: id, name, category.slot."""
    return SimpleNamespace(id=item_id, name=name or f"item {item_id}",
                           category=SimpleNamespace(slot=slot))


def log_look(client, names, day=TODAY):
    return client.post("/planner/log", data={
        "item_ids": ids(*names), "date": day.strftime("%d.%m.%Y"),
    }, follow_redirects=True)


def logs():
    return db.session.scalars(db.select(WearLog).order_by(WearLog.id)).all()


# ---------- the check, no Flask needed ----------

def test_combo_is_top_and_bottom_or_a_dress():
    tee, jeans, shoes, dress = fake(1, "top"), fake(2, "bottom"), fake(3, "feet"), fake(4, "full")
    assert combo_ids([tee, jeans, shoes]) == {1, 2}  # shoes don't count
    assert combo_ids([dress, shoes]) == {4}
    assert combo_ids([tee, shoes]) == set()          # a top alone isn't a combo


def test_matching_days_uses_subsets():
    worn = {WED: {1, 2, 3}, WED + timedelta(days=1): {1, 5}}
    assert matching_days({1, 2}, worn) == [WED]  # extra items that day are fine
    assert matching_days({1, 5, 9}, worn) == []
    assert matching_days(set(), worn) == []


def test_notice_names_the_items_and_the_day():
    items = [fake(1, "top", "White tee"), fake(2, "bottom", "Blue jeans"), fake(3, "feet", "Sneakers")]
    assert combo_notice(items, [WED]) == "You wore White tee with Blue jeans on Wednesday 07.10.2026."
    assert combo_notice(items, []) is None


# ---------- the wear log ----------

def test_mark_worn_writes_the_wear_log(client):
    weekend, _ = setup_outfits(client)
    plan(client, weekend, TODAY)
    entry = entry_for(weekend, TODAY)
    client.post(f"/planner/{entry.id}/worn")
    [log] = logs()
    assert log.outfit_id == weekend.id and log.date == TODAY
    assert {item.name for item in log.items} == {"White tee", "Blue jeans", "Sneakers"}

    client.post(f"/planner/{entry.id}/worn")  # untick
    assert logs() == [] and get_item("White tee").times_worn == 0


def test_deleting_things_keeps_the_log_tidy(client):
    weekend, _ = setup_outfits(client)
    plan(client, weekend, TODAY)
    client.post(f"/planner/{entry_for(weekend, TODAY).id}/worn")
    client.post(f"/outfits/{weekend.id}/delete")
    [log] = logs()
    assert log.outfit_id is None and len(log.items) == 3  # you did wear them
    client.post(f"/items/{get_item('Sneakers').id}/delete")
    assert {item.name for item in log.items} == {"White tee", "Blue jeans"}


# ---------- the "Log a look" page ----------

def test_log_page_requires_login(client):
    assert client.get("/planner/log").status_code == 302


def test_log_a_look_from_loose_items(client):
    register(client)
    make_basics(client)
    page = client.get("/planner/log").data
    assert b"White tee" in page and b"Nothing yet" in page

    response = log_look(client, ["White tee", "Blue jeans"])
    assert b"Logged your look" in response.data
    [log] = logs()
    assert log.outfit_id is None and len(log.items) == 2
    assert get_item("White tee").times_worn == 1
    assert last_worn_date(get_item("White tee")) == TODAY


def test_same_combo_within_a_week_gets_a_notice(client):
    register(client)
    make_basics(client)
    log_look(client, ["White tee", "Blue jeans"], TODAY - timedelta(days=3))
    response = log_look(client, ["White tee", "Blue jeans", "Sneakers"])
    assert b"You wore White tee with Blue jeans on" in response.data
    assert len(logs()) == 2  # a note, never a block


def test_older_or_different_looks_get_no_notice(client):
    register(client)
    make_basics(client)
    log_look(client, ["White tee", "Blue jeans"], TODAY - timedelta(days=8))
    log_look(client, ["Red dress"], TODAY - timedelta(days=1))
    response = log_look(client, ["White tee", "Blue jeans"])
    assert b"You wore" not in response.data


def test_log_rejects_future_days_and_half_outfits(client):
    register(client)
    make_basics(client)
    response = log_look(client, ["White tee", "Blue jeans"], TODAY + timedelta(days=1))
    assert b"hasn&#39;t happened yet" in response.data
    response = log_look(client, ["White tee"])
    assert b"needs a top and a bottom" in response.data
    assert logs() == []


def test_remove_a_logged_look(client):
    register(client)
    make_basics(client)
    log_look(client, ["Red dress"])
    [log] = logs()
    response = client.post(f"/planner/log/{log.id}/delete", follow_redirects=True)
    assert b"Removed the look" in response.data
    assert logs() == [] and get_item("Red dress").times_worn == 0


def test_planner_looks_are_unticked_in_the_planner(client):
    weekend, _ = setup_outfits(client)
    plan(client, weekend, TODAY)
    client.post(f"/planner/{entry_for(weekend, TODAY).id}/worn")
    [log] = logs()
    response = client.post(f"/planner/log/{log.id}/delete", follow_redirects=True)
    assert b"came from the planner" in response.data
    assert len(logs()) == 1


def test_you_cannot_touch_someone_elses_log(client):
    register(client)
    make_basics(client)
    log_look(client, ["Red dress"])
    log_id = logs()[0].id
    logout(client)
    register(client, username="bob", email="bob@example.com")
    assert client.post(f"/planner/log/{log_id}/delete").status_code == 404
    page = client.get("/planner/log").data
    assert b"Red dress" not in page  # not in bob's picker or his last 7 days


# ---------- the notice in the builder, the API and the planner ----------

def test_api_check_tells_about_the_combo(client):
    register(client)
    make_basics(client)
    log_look(client, ["White tee", "Blue jeans"], WED)
    body = {"item_ids": ids("White tee", "Blue jeans")}
    friday = client.post("/api/outfits/check", json={**body, "date": "09.10.2026"}).get_json()
    assert friday["combo"] == "You wore White tee with Blue jeans on Wednesday 07.10.2026."
    later = client.post("/api/outfits/check", json={**body, "date": "2026-10-20"}).get_json()
    assert later["combo"] is None


def test_planning_the_same_combo_again_says_so(client):
    weekend, _ = setup_outfits(client)
    yesterday = TODAY - timedelta(days=1)
    log_look(client, ["White tee", "Blue jeans"], yesterday)
    response = plan(client, weekend, TODAY)
    assert b"You wore White tee with Blue jeans on" in response.data

    save_outfit(client, name="Again", item_ids=ids("White tee", "Blue jeans"))
    data = client.post("/api/schedule", json={
        "outfit_id": get_outfit("Again").id, "date": (TODAY + timedelta(days=1)).isoformat(),
    }).get_json()
    assert data["notice"].startswith("You wore White tee with Blue jeans on")
