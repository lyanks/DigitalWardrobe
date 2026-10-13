"""Trips on the calendar: which trip (if any) covers each day."""
from app.extensions import db
from app.models import Trip


def trips_between(user_id, start, end):
    """Trips that overlap start..end, earliest first.

    Two date ranges overlap when each one starts before the other ends:
    trip.start <= end AND trip.end >= start. (Draw it on paper: every
    other case is "completely before" or "completely after".)
    """
    return db.session.scalars(
        db.select(Trip).filter_by(user_id=user_id)
        .where(Trip.start_date <= end, Trip.end_date >= start)
        .order_by(Trip.start_date)
    ).all()


def trip_for_each_day(trips, days):
    """{day: trip} for every day that falls inside one of the trips."""
    covered = {}
    for trip in trips:
        for day in days:
            if trip.covers(day):
                covered.setdefault(day, trip)  # overlapping trips: the earlier one
    return covered
