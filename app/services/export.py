"""Download my data: everything you put in the app, as one zip file.

data.json holds your profile, clothes, outfits, plans, wear log, trips
and ideas, in plain JSON that any program can read. photos/ holds every
picture you uploaded, under the same names data.json uses. Dates are
written as 2026-11-07 (ISO): the standard for files, unlike the screen.

Why: your data is yours. You can keep a copy, move to another app, or
check exactly what this one stores about you.
"""
import io
import json
import os
import zipfile

from app.guests import upload_folder


def _day(value):
    return value.isoformat() if value else None


def collect(user):
    """Everything about `user` as plain dicts and lists."""
    return {
        "profile": {
            "username": user.username, "email": user.email, "display_name": user.display_name,
            "language": user.language, "theme": user.theme, "undertone": user.undertone,
            "body_shape": user.body_shape, "member_since": _day(user.created_at),
        },
        "items": [{
            "id": item.id, "name": item.name, "category": item.category.name, "color": item.color,
            "brand": item.brand, "size": item.size, "seasons": item.seasons, "styles": item.styles,
            "moods": item.moods, "status": item.status, "times_worn": item.times_worn,
            "purchase_date": _day(item.purchase_date), "notes": item.notes,
            "price": str(item.price) if item.price is not None else None, "currency": item.currency,
            "shop_url": item.shop_url, "photo": item.image_path,
        } for item in user.items],
        "outfits": [{
            "id": outfit.id, "name": outfit.name, "occasion": outfit.occasion, "notes": outfit.notes,
            "item_ids": [item.id for item in outfit.items], "photo": outfit.image_path,
        } for outfit in user.outfits],
        "planned": [{
            "date": _day(entry.date), "outfit_id": entry.outfit_id, "note": entry.note,
        } for entry in user.schedule],
        "worn": [{
            "date": _day(log.date), "item_ids": [item.id for item in log.items],
        } for log in user.wear_logs],
        "trips": [{
            "name": trip.name, "from": _day(trip.start_date), "to": _day(trip.end_date),
            "item_ids": [link.item_id for link in trip.item_links],
        } for trip in user.trips],
        "ideas": [{
            "title": idea.title, "note": idea.note, "link": idea.source_url,
            "picture_url": idea.image_url, "photo": idea.image_path,
        } for idea in user.ideas],
    }


def build_zip(user):
    """The zip file's bytes."""
    data = collect(user)
    photos = [user.avatar_path] + [row.get("photo") for key in ("items", "outfits", "ideas")
                                   for row in data[key]]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("data.json", json.dumps(data, ensure_ascii=False, indent=2))
        folder = upload_folder()
        for photo in filter(None, photos):
            path = os.path.join(folder, photo)
            if os.path.isfile(path):
                archive.write(path, f"photos/{photo}")
    return buffer.getvalue()
