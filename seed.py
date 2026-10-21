"""Fill the database with the starting lists the app needs.

Run once after `flask db upgrade`:   python seed.py
Running it again is safe: it only fills a list that is still empty, so
what the admin changed on /admin/options is never undone.
"""
from app import create_app
from app.extensions import db
from app.models import Category, Option
from app.wardrobe.choices import CATEGORIES, COLORS, OCCASIONS, SEASONS, STYLES


def seed_categories():
    if db.session.scalar(db.select(Category).limit(1)):
        return 0
    for position, (name, slot) in enumerate(CATEGORIES):
        db.session.add(Category(name=name, slot=slot, position=position))
    db.session.commit()
    return len(CATEGORIES)


def seed_options():
    """Colours, seasons, styles and occasions (the lists in wardrobe/choices.py)."""
    added = 0
    starting = {
        "color": list(COLORS.items()),
        "season": [(value, None) for value in SEASONS],
        "style": [(value, None) for value in STYLES],
        "occasion": [(value, None) for value in OCCASIONS],
    }
    for kind, rows in starting.items():
        if db.session.scalar(db.select(Option).filter_by(kind=kind).limit(1)):
            continue
        for position, (value, hex_value) in enumerate(rows):
            db.session.add(Option(kind=kind, value=value, hex=hex_value, position=position))
            added += 1
    db.session.commit()
    return added


if __name__ == "__main__":
    app = create_app()
    # Outside a request, Flask needs an "app context" to know which
    # app (and which database) db.session belongs to.
    with app.app_context():
        print(f"Added {seed_categories()} categories and {seed_options()} options.")
