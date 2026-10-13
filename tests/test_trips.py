"""Pack a suitcase: trips on the calendar and the drag-and-drop pack page."""
from datetime import date, timedelta

from app.extensions import db
from app.models import Trip, TripItem
from app.services.trips import trip_for_each_day, trips_between
from tests.conftest import logout, register
from tests.test_items import get_item
from tests.test_outfits import get_outfit, ids, make_basics, save_outfit
from tests.test_planner import TODAY

JSON = {"Accept": "application/json"}


def new_trip(client, name="Lviv weekend", start=TODAY, days=3, **extra):
    end = start + timedelta(days=days - 1)
    return client.post("/trips", data={
        "name": name, "start_date": start.strftime("%d.%m.%Y"),
        "end_date": end.strftime("%d.%m.%Y"), **extra,
    }, follow_redirects=True)


def get_trip(name="Lviv weekend"):
    return db.session.scalar(db.select(Trip).filter_by(name=name))


def setup_trip(client):
    register(client)
    make_basics(client)
    new_trip(client)
    return get_trip()


def links():
    return db.session.scalars(db.select(TripItem)).all()


# ---------- which days a trip covers, no Flask needed ----------

def test_trip_for_each_day():
    trip = Trip(name="A", start_date=date(2026, 10, 14), end_date=date(2026, 10, 16))
    days = [date(2026, 10, 13) + timedelta(days=n) for n in range(5)]
    covered = trip_for_each_day([trip], days)
    assert sorted(covered) == [date(2026, 10, 14), date(2026, 10, 15), date(2026, 10, 16)]
    assert trip.days == 3


# ---------- creating trips ----------

def test_trips_require_login(client):
    assert client.get("/trips").status_code == 302


def test_create_a_trip_and_land_on_the_pack_page(client):
    register(client)
    make_basics(client)
    page = new_trip(client).get_data(as_text=True)
    assert "Trip “Lviv weekend” is on your calendar" in page
    assert "Suitcase" in page and "White tee" in page
    assert f"{TODAY.strftime('%d.%m.%Y')} – " in page and "· 3 days" in page
    assert "Lviv weekend" in client.get("/trips").get_data(as_text=True)


def test_end_before_start_and_too_long_are_refused(client):
    register(client)
    page = new_trip(client, days=0).get_data(as_text=True)
    assert "can&#39;t end before it starts" in page
    page = new_trip(client, days=61).get_data(as_text=True)
    assert "60 days" in page
    assert db.session.scalars(db.select(Trip)).all() == []


def test_edit_and_delete_a_trip(client):
    trip = setup_trip(client)
    client.post(f"/trips/{trip.id}/items/{get_item('White tee').id}")
    client.post(f"/trips/{trip.id}/edit", data={
        "name": "Kyiv", "start_date": TODAY.strftime("%d.%m.%Y"),
        "end_date": (TODAY + timedelta(days=1)).strftime("%d.%m.%Y"),
    })
    assert get_trip("Kyiv").days == 2
    page = client.post(f"/trips/{trip.id}/delete", follow_redirects=True).get_data(as_text=True)
    assert "Your clothes are still in your wardrobe" in page
    assert links() == [] and get_item("White tee") is not None


# ---------- filling the suitcase ----------

def test_add_pack_and_remove_with_json(client):
    trip = setup_trip(client)
    tee = get_item("White tee").id
    data = client.post(f"/trips/{trip.id}/items/{tee}", headers=JSON).get_json()
    assert data["added"] == [tee] and data["count"] == 1 and data["packed"] == 0
    assert "White tee" in data["html"] and 'data-item-id="%d"' % tee in data["html"]

    again = client.post(f"/trips/{trip.id}/items/{tee}", headers=JSON).get_json()
    assert again["added"] == [] and again["count"] == 1  # no duplicates

    data = client.post(f"/trips/{trip.id}/items/{tee}/packed", headers=JSON).get_json()
    assert data == {"item": tee, "is_packed": True, "count": 1, "packed": 1}

    data = client.post(f"/trips/{trip.id}/items/{tee}/remove", headers=JSON).get_json()
    assert data == {"removed": tee, "count": 0, "packed": 0}
    assert links() == []


def test_plain_forms_work_without_javascript(client):
    trip = setup_trip(client)
    tee = get_item("White tee").id
    response = client.post(f"/trips/{trip.id}/items/{tee}")
    assert response.status_code == 302 and response.headers["Location"].endswith(f"/trips/{trip.id}")
    client.post(f"/trips/{trip.id}/items/{tee}/packed")
    page = client.get(f"/trips/{trip.id}").get_data(as_text=True)
    assert "1 of 1 packed" in page and "in-suitcase" in page


def test_a_whole_outfit_goes_in_at_once(client):
    trip = setup_trip(client)
    save_outfit(client, name="Weekend", item_ids=ids("White tee", "Blue jeans", "Sneakers"))
    client.post(f"/trips/{trip.id}/items/{get_item('Sneakers').id}")
    data = client.post(f"/trips/{trip.id}/outfits/{get_outfit('Weekend').id}", headers=JSON).get_json()
    assert data["added"] == sorted(ids("White tee", "Blue jeans"))  # sneakers were already in
    assert data["count"] == 3


def test_items_in_the_wash_get_a_note_in_the_suitcase(client):
    trip = setup_trip(client)
    tee = get_item("White tee").id
    client.post(f"/items/{tee}/laundry")
    data = client.post(f"/trips/{trip.id}/items/{tee}", headers=JSON).get_json()
    assert "wash it first" in data["html"]


def test_deleting_an_item_takes_it_out_of_the_suitcase(client):
    trip = setup_trip(client)
    tee = get_item("White tee").id
    client.post(f"/trips/{trip.id}/items/{tee}")
    client.post(f"/items/{tee}/delete")
    assert links() == [] and get_trip().item_links == []


def test_someone_elses_trip_and_clothes_are_404(client):
    trip = setup_trip(client)
    tee = get_item("White tee").id
    logout(client)
    register(client, username="bob", email="bob@example.com")
    assert client.get(f"/trips/{trip.id}").status_code == 404
    assert client.post(f"/trips/{trip.id}/items/{tee}").status_code == 404
    new_trip(client, name="Bob's trip")
    bobs = get_trip("Bob's trip")
    assert client.post(f"/trips/{bobs.id}/items/{tee}").status_code == 404  # alice's tee


# ---------- the calendar and the home page ----------

def test_trip_shows_on_the_planner_and_home(client):
    trip = setup_trip(client)
    assert trips_between(trip.user_id, TODAY, TODAY) == [trip]
    page = client.get("/planner").get_data(as_text=True)
    assert "trip-bar trip-start" in page and "Lviv weekend" in page
    assert "Pack a suitcase" in page
    home = client.get("/").get_data(as_text=True)
    assert 'class="week-trip"' in home
