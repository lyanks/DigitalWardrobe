"""The outfit board: where each item sits when an outfit is shown as a
collage (like a Pinterest board) instead of a row of photos.

Plain Python, no Flask: the routes and templates call these functions.

Every position is in % of the board, so the same outfit looks the same on
a phone and on a laptop:
  x, y   the left and top edge of the picture
  width  the picture's width (its height follows the photo's shape)
  layer  higher numbers are drawn on top (CSS z-index)
"""
import json

# Where an item goes the first time, by body slot: (x, y, width).
# The board is 4 wide by 5 high (CSS aspect-ratio: 4 / 5). It's a flat
# lay, like a Pinterest board: jacket and top side by side at the top,
# the bottom under them, shoes and accessories down the right.
SPOTS = {
    "outer": (2, 3, 42),
    "top": (40, 3, 42),
    "full": (26, 3, 46),       # a dress takes the middle
    "bottom": (8, 40, 36),
    "feet": (50, 80, 34),
    "accessory": (64, 38, 28),  # a column on the right
}
# Which slot sits on top of which: shoes at the back, accessories in front.
LAYERS = {"feet": 1, "bottom": 2, "full": 3, "top": 3, "outer": 4, "accessory": 5}

# Limits, so a broken or edited request can't put a piece miles away.
MIN_WIDTH, MAX_WIDTH = 5, 100
MIN_POS, MAX_POS = -50, 100
MAX_LAYER = 999


def default_spot(slot, nth=0):
    """Where the nth item of a slot goes when it was never moved.

    Accessories go down the right-hand column; a second top (or any other
    repeat) is nudged a little so it doesn't hide exactly behind the first.
    """
    x, y, width = SPOTS.get(slot, SPOTS["accessory"])
    if slot == "accessory":
        y += (nth % 3) * 14
    else:
        x, y = x + nth * 6, y + nth * 6
    return {"x": x, "y": y, "width": width, "layer": LAYERS.get(slot, 5)}


def place(item, link=None, nth=0):
    """The board position of one item: saved on its link, or the default."""
    if link is not None and link.board_x is not None:
        return {"x": link.board_x, "y": link.board_y, "width": link.board_width, "layer": link.board_layer or 0}
    return default_spot(item.category.slot, nth)


def board_pieces(links):
    """[(item, position), ...] for an outfit's item links, back to front."""
    seen = {}
    pieces = []
    for link in links:
        slot = link.item.category.slot
        pieces.append((link.item, place(link.item, link, seen.get(slot, 0))))
        seen[slot] = seen.get(slot, 0) + 1
    return sorted(pieces, key=lambda piece: piece[1]["layer"])


def editor_spots(items, links, layout=None):
    """Positions for every item on the outfit form's board.

    Returns two dicts {item_id: position}: where each piece is now (the
    layout just sent, if the form came back with an error; else what's
    saved; else the default), and each piece's default (for Reset).
    """
    saved = {link.item_id: link for link in links}
    layout = layout or {}
    counts = {}
    spots, defaults = {}, {}
    for item in items:
        slot = item.category.slot
        nth = counts.get(slot, 0) if slot == "accessory" else 0
        counts[slot] = counts.get(slot, 0) + 1
        defaults[item.id] = default_spot(slot, nth)
        spots[item.id] = layout.get(item.id) or place(item, saved.get(item.id), nth)
    return spots, defaults


def _clamp(value, low, high):
    return max(low, min(high, value))


def parse_layout(text, allowed_ids):
    """Read the layout the board's JavaScript sent with the form.

    It's JSON like {"12": {"x": 30, "y": 4, "width": 42, "layer": 3}, ...}.
    Anything that came from the browser can be broken or tampered with,
    so: bad JSON gives {}, unknown item ids are skipped, numbers are
    clamped to sensible limits, and a piece with a non-number is skipped.
    Returns {item_id: {"x", "y", "width", "layer"}}.
    """
    try:
        data = json.loads(text or "{}")
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    layout = {}
    for key, piece in data.items():
        try:
            item_id = int(key)
            x, y, width = float(piece["x"]), float(piece["y"]), float(piece["width"])
            layer = int(piece["layer"])
        except (KeyError, TypeError, ValueError):
            continue
        if item_id not in allowed_ids or any(v != v for v in (x, y, width)):  # v != v: NaN
            continue
        layout[item_id] = {
            "x": round(_clamp(x, MIN_POS, MAX_POS), 2),
            "y": round(_clamp(y, MIN_POS, MAX_POS), 2),
            "width": round(_clamp(width, MIN_WIDTH, MAX_WIDTH), 2),
            "layer": _clamp(layer, 0, MAX_LAYER),
        }
    return layout


def apply_layout(links, layout):
    """Copy the parsed layout onto the outfit's links. Items without an
    entry keep what they had (or stay "never arranged")."""
    for link in links:
        piece = layout.get(link.item_id if link.item_id is not None else link.item.id)
        if piece:
            link.board_x, link.board_y = piece["x"], piece["y"]
            link.board_width, link.board_layer = piece["width"], piece["layer"]
