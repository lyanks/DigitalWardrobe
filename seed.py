"""Fill the database with the fixed data the app needs.

Run once after `flask db upgrade`:   python seed.py
Running it again is safe: it only adds what is missing.
"""
from app import create_app
from app.extensions import db
from app.models import Category
from app.wardrobe.choices import CATEGORIES


def seed_categories():
    existing = {c.name for c in db.session.scalars(db.select(Category))}
    added = 0
    for name, slot in CATEGORIES:
        if name not in existing:
            db.session.add(Category(name=name, slot=slot))
            added += 1
    db.session.commit()
    return added


if __name__ == "__main__":
    app = create_app()
    # Outside a request, Flask needs an "app context" to know which
    # app (and which database) db.session belongs to.
    with app.app_context():
        print(f"Added {seed_categories()} categories.")
