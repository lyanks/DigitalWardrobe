"""The rules for what counts as a wearable outfit.

This file knows nothing about Flask, forms or the database: it takes a list
of items and answers with a list of problems. That keeps the rules easy to
read, easy to test, and usable from any route (the builder now, the planner
in Phase 4).

The texts are wrapped in _() for translation. Outside a request (as in
the tests) _() simply gives the English text back.
"""
from flask_babel import gettext as _

from app.i18n import N_

# Body slots from top to bottom: the order items are shown in an outfit.
SLOT_ORDER = ["outer", "top", "full", "bottom", "feet", "accessory"]

# Slots you may have several of in one outfit. Everything else: one at most.
MULTI_SLOTS = {"accessory"}

# One whole sentence per slot (not "Only one {slot}..."): in Ukrainian the
# words around the slot name change with it. N_() only marks them for
# pybabel; _() translates them when the problem is reported.
TOO_MANY = {
    "outer": N_("Only one outerwear per outfit (you picked %(count)s)."),
    "top": N_("Only one top per outfit (you picked %(count)s)."),
    "full": N_("Only one dress or other full-body item per outfit (you picked %(count)s)."),
    "bottom": N_("Only one bottom per outfit (you picked %(count)s)."),
    "feet": N_("Only one pair of shoes per outfit (you picked %(count)s)."),
}


def outfit_problems(items):
    """Return a list of human-readable problems; an empty list means it's fine."""
    if not items:
        return [_("Pick at least one item.")]

    slots = [item.category.slot for item in items]
    problems = []

    # Something has to cover you: a top with a bottom, or one full-body item.
    has_top_and_bottom = "top" in slots and "bottom" in slots
    if not has_top_and_bottom and "full" not in slots:
        problems.append(_("An outfit needs a top and a bottom, or a dress / full-body item."))

    for slot in SLOT_ORDER:
        count = slots.count(slot)
        if count > 1 and slot not in MULTI_SLOTS:
            problems.append(_(TOO_MANY[slot], count=count))

    return problems


def sort_by_slot(items):
    """Items in head-to-toe order, so every outfit is shown the same way."""
    return sorted(items, key=lambda item: (SLOT_ORDER.index(item.category.slot), item.name.lower()))
