from datetime import date, timedelta

from app.extensions import db
from app.models import ScheduledOutfit
from app.services.planner import month_weeks, parse_month, shift_month
from tests.conftest import logout, register
from tests.test_items import get_item
from tests.test_outfits import get_outfit, ids, make_basics, save_outfit

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)
YESTERDAY = TODAY - timedelta(days=1)


# ---------- the month helpers, no Flask needed ----------

def test_parse_month():
    assert parse_month("2026-10") == date(2026, 10, 1)
    # Nonsense falls back to the current month instead of crashing.
    for text in ("", "banana", "2026-13", None):
        assert parse_month(text, today=date(2026, 5, 17)) == date(2026, 5, 1)


def test_shift_month_crosses_years():
    assert shift_month(date(2026, 12, 1), 1) == date(2027, 1, 1)
    assert shift_month(date(2026, 1, 1), -1) == date(2025, 12, 1)


def test_month_weeks_are_full_weeks_starting_monday():
    weeks = month_weeks(date(2026, 10, 1))
    assert all(len(week) == 7 for week in weeks)
    assert all(week[0].weekday() == 0 for week in weeks)  # 0 = Monday
    # October 2026 starts on a Thursday, so the grid starts on Mon 28 Sep.
    assert weeks[0][0] == date(2026, 9, 28)
    assert date(2026, 10, 31) in weeks[-1]


# ---------- helpers ----------

def setup_outfits(client):
    register(client)
    make_basics(client)
    save_outfit(client, name="Weekend", item_ids=ids("White tee", "Blue jeans", "Sneakers"))
    save_outfit(client, name="Date night", item_ids=ids("Red dress"))
    return get_outfit("Weekend"), get_outfit("Date night")


def plan(client, outfit, day, note=""):
    return client.post("/planner/schedule", data={
        "outfit_id": outfit.id, "date": day.strftime("%d.%m.%Y"), "note": note,
    }, follow_redirects=True)


def entry_for(outfit, day):
    return db.session.scalar(db.select(ScheduledOutfit).filter_by(outfit_id=outfit.id, date=day))


# ---------- the planner page ----------

def test_planner_requires_login(client):
    assert client.get("/planner").status_code == 302


def test_planner_shows_the_month(client):
    setup_outfits(client)
    page = client.get("/planner?month=2026-10").data
    assert b"October 2026" in page
    assert b"September" in page and b"November" in page  # prev / next links
    assert b'data-date="2026-09-28"' in page              # grid starts on a Monday
    assert b"Weekend" in page                              # outfit chips


def test_schedule_with_the_form(client):
    weekend, _ = setup_outfits(client)
    response = plan(client, weekend, TOMORROW, note="Picnic")
    assert b"Planned \xe2\x80\x9cWeekend\xe2\x80\x9d" in response.data
    entry = entry_for(weekend, TOMORROW)
    assert entry.note == "Picnic" and entry.worn is False
    assert b"Picnic" in response.data  # shown in the calendar


def test_same_outfit_twice_on_one_day_is_refused(client):
    weekend, date_night = setup_outfits(client)
    plan(client, weekend, TOMORROW)
    response = plan(client, weekend, TOMORROW)
    assert b"already planned for that day" in response.data
    # A different outfit on the same day is fine (day + evening).
    plan(client, date_night, TOMORROW)
    assert db.session.query(ScheduledOutfit).count() == 2


def test_cannot_plan_someone_elses_outfit(client):
    weekend, _ = setup_outfits(client)
    logout(client)
    register(client, username="bob", email="bob@example.com")
    response = plan(client, weekend, TOMORROW)
    assert b"Not a valid choice" in response.data
    assert db.session.query(ScheduledOutfit).count() == 0


# ---------- worn ----------

def test_mark_worn_counts_each_item_and_can_be_undone(client):
    weekend, _ = setup_outfits(client)
    plan(client, weekend, YESTERDAY)
    entry = entry_for(weekend, YESTERDAY)

    client.post(f"/planner/{entry.id}/worn", follow_redirects=True)
    assert entry.worn
    for name in ("White tee", "Blue jeans", "Sneakers"):
        assert get_item(name).times_worn == 1
    assert get_item("Red dress").times_worn == 0

    client.post(f"/planner/{entry.id}/worn", follow_redirects=True)  # untick
    assert not entry.worn
    assert get_item("White tee").times_worn == 0


def test_future_day_cannot_be_marked_worn(client):
    weekend, _ = setup_outfits(client)
    plan(client, weekend, TOMORROW)
    entry = entry_for(weekend, TOMORROW)
    response = client.post(f"/planner/{entry.id}/worn", follow_redirects=True)
    assert b"in the future" in response.data
    assert not entry.worn and get_item("White tee").times_worn == 0


def test_unscheduling_a_worn_outfit_takes_the_wears_back(client):
    weekend, _ = setup_outfits(client)
    plan(client, weekend, TODAY)
    entry = entry_for(weekend, TODAY)
    client.post(f"/planner/{entry.id}/worn")
    assert get_item("White tee").times_worn == 1

    client.post(f"/planner/{entry.id}/delete", follow_redirects=True)
    assert db.session.query(ScheduledOutfit).count() == 0
    assert get_item("White tee").times_worn == 0


def test_other_users_entries_are_404(client):
    weekend, _ = setup_outfits(client)
    plan(client, weekend, TODAY)
    entry_id = entry_for(weekend, TODAY).id
    logout(client)
    register(client, username="bob", email="bob@example.com")
    assert client.post(f"/planner/{entry_id}/worn").status_code == 404
    assert client.post(f"/planner/{entry_id}/delete").status_code == 404


def test_deleting_outfit_removes_it_from_the_planner_but_keeps_wears(client):
    weekend, _ = setup_outfits(client)
    plan(client, weekend, TODAY)
    client.post(f"/planner/{entry_for(weekend, TODAY).id}/worn")

    assert b"taken off the planner" in client.get(f"/outfits/{weekend.id}/delete").data
    client.post(f"/outfits/{weekend.id}/delete")
    assert db.session.query(ScheduledOutfit).count() == 0
    assert get_item("White tee").times_worn == 1  # you did wear it


# ---------- home page and outfit page ----------

def test_home_shows_today_and_this_week(client):
    weekend, date_night = setup_outfits(client)
    plan(client, weekend, TODAY, note="Market")
    plan(client, date_night, TODAY + timedelta(days=3))
    plan(client, date_night, TODAY + timedelta(days=10))  # too far ahead

    page = client.get("/").data.decode()
    today_part, week_part = page.split("This week")
    assert "Weekend" in today_part and "Market" in today_part
    assert week_part.count("Date night") == 1


def test_outfit_page_sums_up_its_days(client):
    weekend, _ = setup_outfits(client)
    plan(client, weekend, YESTERDAY)
    client.post(f"/planner/{entry_for(weekend, YESTERDAY).id}/worn")
    soon = TODAY + timedelta(days=30)
    plan(client, weekend, soon)

    page = client.get(f"/outfits/{weekend.id}").data.decode()
    # One short line: how often planned and worn, and the next day.
    assert f"Planned 2×, worn 1× · next {soon.strftime('%a %d.%m')}" in page
    # The days themselves sit inside the closed <details> as chips.
    assert soon.strftime("%d.%m") in page and "<details" in page


# ---------- JSON API ----------

def test_api_schedule(client):
    weekend, _ = setup_outfits(client)
    response = client.post("/api/schedule", json={"outfit_id": weekend.id, "date": TOMORROW.isoformat()})
    assert response.status_code == 201
    data = response.get_json()
    assert data["outfit"]["name"] == "Weekend" and data["date"] == TOMORROW.isoformat()
    assert data["date_text"] == TOMORROW.strftime("%d.%m.%Y")
    assert "entry" in data["html"]  # the snippet calendar.js inserts
    assert entry_for(weekend, TOMORROW) is not None

    # Second time: 409 Conflict, with a message for the page.
    again = client.post("/api/schedule", json={"outfit_id": weekend.id, "date": TOMORROW.isoformat()})
    assert again.status_code == 409 and "already planned" in again.get_json()["error"]


def test_api_schedule_bad_input(client):
    weekend, _ = setup_outfits(client)
    assert client.post("/api/schedule", json={"outfit_id": weekend.id, "date": "14/10"}).status_code == 400
    assert client.post("/api/schedule", json={"outfit_id": "x", "date": "2026-10-14"}).status_code == 400
    assert client.post("/api/schedule", data="not json").status_code == 400
    assert client.post("/api/schedule", json={"outfit_id": 999, "date": "2026-10-14"}).status_code == 404


def test_api_schedule_other_users_outfit_is_404(client):
    weekend, _ = setup_outfits(client)
    logout(client)
    register(client, username="bob", email="bob@example.com")
    response = client.post("/api/schedule", json={"outfit_id": weekend.id, "date": "2026-10-14"})
    assert response.status_code == 404


def test_api_check_outfit(client):
    setup_outfits(client)
    ok = client.post("/api/outfits/check", json={"item_ids": ids("White tee", "Blue jeans")})
    assert ok.status_code == 200 and ok.get_json() == {"problems": [], "combo": None}

    missing = client.post("/api/outfits/check", json={"item_ids": ids("White tee")})
    assert "a top and a bottom" in missing.get_json()["problems"][0]

    assert client.post("/api/outfits/check", json={"item_ids": [999]}).status_code == 404
    assert client.post("/api/outfits/check", json={"item_ids": "3"}).status_code == 400


def test_api_requires_login(client):
    response = client.post("/api/schedule", json={"outfit_id": 1, "date": "2026-10-14"})
    assert response.status_code == 302


# ---------- dates are typed and shown as dd.mm.yyyy ----------

def test_date_field_accepts_day_month_year(client):
    weekend, _ = setup_outfits(client)
    for typed in ("05.11.2026", "06/11/2026", " 07-11-2026 "):
        client.post("/planner/schedule", data={"outfit_id": weekend.id, "date": typed})
    assert [e.date for e in weekend.schedule] == [date(2026, 11, 5), date(2026, 11, 6), date(2026, 11, 7)]


def test_wrong_date_format_is_explained(client):
    weekend, _ = setup_outfits(client)
    response = client.post("/planner/schedule", data={"outfit_id": weekend.id, "date": "2026-11-05"},
                           follow_redirects=True)
    assert b"dd.mm.yyyy" in response.data
    assert db.session.query(ScheduledOutfit).count() == 0


def test_planner_form_is_prefilled_as_day_month_year(client):
    setup_outfits(client)
    page = client.get("/planner").data.decode()
    assert f'value="{TODAY.strftime("%d.%m.%Y")}"' in page
