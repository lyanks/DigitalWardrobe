"""The rules for what counts as a wearable outfit.

This file knows nothing about Flask, forms or the database: it takes a list
of items and answers with a list of problems. That keeps the rules easy to
read, easy to test, and usable from any route (the builder now, the planner
in Phase 4).
"""

# Body slots from top to bottom: the order items are shown in an outfit.
SLOT_ORDER = ["outer", "top", "full", "bottom", "feet", "accessory"]

# Slots you may have several of in one outfit. Everything else: one at most.
MULTI_SLOTS = {"accessory"}

SLOT_NAMES = {
    "outer": "outerwear",
    "top": "top",
    "full": "dress or other full-body item",
    "bottom": "bottom",
    "feet": "pair of shoes",
    "accessory": "accessory",
}


def outfit_problems(items):
    """Return a list of human-readable problems; an empty list means it's fine."""
    if not items:
        return ["Pick at least one item."]

    slots = [item.category.slot for item in items]
    problems = []

    # Something has to cover you: a top with a bottom, or one full-body item.
    has_top_and_bottom = "top" in slots and "bottom" in slots
    if not has_top_and_bottom and "full" not in slots:
        problems.append("An outfit needs a top and a bottom, or a dress / full-body item.")

    for slot in SLOT_ORDER:
        count = slots.count(slot)
        if count > 1 and slot not in MULTI_SLOTS:
            problems.append(f"Only one {SLOT_NAMES[slot]} per outfit (you picked {count}).")

    return problems


def sort_by_slot(items):
    """Items in head-to-toe order, so every outfit is shown the same way."""
    return sorted(items, key=lambda item: (SLOT_ORDER.index(item.category.slot), item.name.lower()))
