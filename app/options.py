"""The shared lists: categories, colours, seasons, styles and occasions.

They live in the database (Category and Option), so the admin can change
them on /admin/options. Everything else asks this module instead of
reading the tables itself.

Pages ask for these lists many times while they're drawn, so each list is
read once and kept in `g` (Flask's per-request scratch space). forget()
throws that copy away after the admin changes something.
"""
from flask import g

from app.extensions import db

# kind -> the column that stores it, filled in by uses() below.
KINDS = ("color", "season", "style", "occasion")
SLOTS = ("top", "bottom", "full", "outer", "feet", "accessory")
GREY = "#9a9a9a"


def _cached(key, load):
    cache = g.setdefault("_options", {})
    if key not in cache:
        cache[key] = load()
    return cache[key]


def forget():
    """Call after changing an option, so the next read sees the change."""
    g.pop("_options", None)


def options(kind, include_hidden=False):
    """Option rows of one kind, in the admin's order."""
    from app.models import Option
    rows = _cached(kind, lambda: db.session.scalars(
        db.select(Option).filter_by(kind=kind).order_by(Option.position, Option.id)
    ).all())
    return rows if include_hidden else [row for row in rows if not row.hidden]


def values(kind, include_hidden=False):
    """["casual", "formal", ...]: what the forms offer and the filters accept."""
    return [row.value for row in options(kind, include_hidden)]


def colors(include_hidden=True):
    """{"black": "#1f1f1f", ...} in the admin's order: the colour dots."""
    return {row.value: row.hex or GREY for row in options("color", include_hidden)}


def swatch(color_name):
    """"blue" -> "#3b6fd1". Unknown -> grey."""
    return colors().get(color_name, GREY)


def categories(include_hidden=False):
    from app.models import Category
    rows = _cached("category", lambda: db.session.scalars(
        db.select(Category).order_by(Category.position, Category.id)
    ).all())
    return rows if include_hidden else [row for row in rows if not row.hidden]


def ukrainian_names():
    """{"Tops": "Верх", "teal": "Бірюзовий", ...}: names the admin typed in."""
    def load():
        names = {}
        for kind in KINDS:
            names.update({row.value: row.name_uk for row in options(kind, True) if row.name_uk})
        names.update({row.name: row.name_uk for row in categories(True) if row.name_uk})
        return names
    return _cached("uk", load)


def uses(kind, value):
    """How many items (or outfits, for occasions) use this value."""
    from app.models import Item, Outfit
    column = {"color": Item.color, "season": Item.season, "style": Item.style,
              "occasion": Outfit.occasion}[kind]
    return db.session.scalar(db.select(db.func.count()).where(column == value))


def rename(kind, old, new):
    """Change the value on every item (or outfit) that has the old one."""
    from app.models import Item, Outfit
    model, column = {"color": (Item, "color"), "season": (Item, "season"),
                     "style": (Item, "style"), "occasion": (Outfit, "occasion")}[kind]
    db.session.execute(
        db.update(model).where(getattr(model, column) == old).values({column: new})
    )
