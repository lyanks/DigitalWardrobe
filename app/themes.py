"""Idea #5: themes and an accent colour.

The colours themselves live in main.css, one block per theme:
    [data-theme="light"] { --color-bg: ...; }
base.html puts the user's choice on <html data-theme="...">, so the
matching block switches every colour at once. This module only knows the
names, and works out a readable text colour for a custom accent.
"""
import re

DEFAULT_THEME = "midnight"

# key -> (label, three colours for the little preview: background, card, accent)
THEMES = {
    "midnight": ("Midnight", ("#0c0b14", "#16141f", "#b99bff")),
    "graphite": ("Graphite", ("#121214", "#1c1c20", "#c4a8ff")),
    "lavender": ("Lavender", ("#f8f7fc", "#ffffff", "#6157ae")),
    "linen": ("Linen", ("#f5efe6", "#fffaf3", "#9a5b3a")),
}

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def text_on(hex_color):
    """Black-ish or white text, whichever is easier to read on this colour.

    Uses "relative luminance" (how bright a colour looks to people): green
    looks much brighter than blue at the same strength, hence the weights.
    """
    red, green, blue = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "#1d0b3a" if luminance > 0.45 else "#ffffff"
