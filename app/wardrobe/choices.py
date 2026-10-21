"""Starting lists, and the fixed ones.

Categories, colours, seasons, styles and occasions now live in the
database (app/options.py), and the admin changes them on /admin/options.
The lists below are only what seed.py puts there on a fresh database.
Currencies and priorities are still fixed here.
"""

# (name, slot). The slot says where it goes on the body; Phase 3's outfit
# builder uses it ("one top + one bottom, or one full-body item").
CATEGORIES = [
    ("Tops", "top"),
    ("Bottoms", "bottom"),
    ("Dresses", "full"),
    ("Outerwear", "outer"),
    ("Shoes", "feet"),
    ("Accessories", "accessory"),
]

# A fixed palette instead of free text, so "Navy", "navy" and "dark blue"
# don't become three different colors in filters and future charts.
# The hex value is only used to draw the little color dot.
COLORS = {
    "black": "#1f1f1f",
    "white": "#f7f7f5",
    "grey": "#9a9a9a",
    "beige": "#d9c7a7",
    "brown": "#7b5435",
    "navy": "#1f2f57",
    "blue": "#3b6fd1",
    "light blue": "#9cc3ea",
    "green": "#3f8a4f",
    "olive": "#76783a",
    "yellow": "#f0cd3c",
    "orange": "#e88a2e",
    "red": "#c7372f",
    "burgundy": "#7a2234",
    "pink": "#f2a5b8",
    "purple": "#7a5c99",
    "multicolor": "linear-gradient(135deg, #c7372f, #f0cd3c, #3f8a4f, #3b6fd1)",
}

SEASONS = ["all", "spring", "summer", "autumn", "winter"]

STYLES = ["casual", "formal", "business", "sporty", "streetwear", "classic", "party", "home"]

# What an outfit is for. Optional on the outfit form.
OCCASIONS = ["casual", "work", "formal", "party", "date", "sport", "travel", "home"]

# Wishlist. The first currency is the default in the form.
CURRENCIES = ["UAH", "EUR", "USD", "PLN", "GBP"]

# priority number -> label. Smaller = more important, so ORDER BY priority
# puts must-haves first.
PRIORITIES = {
    1: "Must have",
    2: "Would be nice",
    3: "Someday",
}
