"""Make a saved pin with your own clothes, with Claude (see ai.py).

The model gets the pin's picture and a short text list of your clean
clothes, one line each:
    12 | top | White linen shirt | white | summer, spring | casual
and answers with the ids of the pieces that recreate the look best, the
pieces you'd still need, and one sentence about it.

The ids go into the JSON schema as "enum" (the only allowed values), so
the answer can only name clothes you really have. The route still
checks them against your wardrobe and the outfit rules.

Cost with Claude Haiku 5.5: the picture is ~1,000-1,600 tokens, 100
items ~1,500, the answer ~300. About $0.001 per suggestion.
"""
import os

from flask import current_app
from flask_babel import gettext as _

from app.services.ai import AiError, ask_claude
from app.services.autotag import small_jpeg

# Plenty for a real wardrobe; keeps the cost of one request bounded.
MAX_ITEMS = 250

PROMPT = """You are a stylist. The picture is an outfit the user saved as inspiration.
Recreate it as closely as possible using ONLY clothes from their wardrobe below.
Pick at most one top, one bottom (or one dress / full-body item instead of both),
one pair of shoes, one outer layer if the picture has one, and up to two accessories.
Match colour first, then shape and mood. Leave a slot empty rather than pick
something that clashes with the look.

Wardrobe (id | slot | name | colour | seasons | styles | moods):
{wardrobe}

Answer with:
- item_ids: the ids you picked
- missing: short names of pieces in the picture they don't own (empty list if none)
- note: one friendly sentence on how the look is recreated, in {language}"""


def wardrobe_lines(items):
    lines = []
    for item in items[:MAX_ITEMS]:
        lines.append(" | ".join([
            str(item.id), item.category.slot, item.name, item.color,
            ", ".join(item.seasons) or "all", ", ".join(item.styles), ", ".join(item.moods),
        ]))
    return "\n".join(lines)


def _schema(ids):
    return {
        "type": "object",
        "properties": {
            "item_ids": {"type": "array", "items": {"type": "integer", "enum": ids}},
            "missing": {"type": "array", "items": {"type": "string"}},
            "note": {"type": "string"},
        },
        "required": ["item_ids", "missing", "note"],
        "additionalProperties": False,
    }


def _picture(idea):
    """(bytes, None) for our own copy of the pin, or (None, url)."""
    if idea.image_path:
        from app.guests import upload_folder
        path = os.path.join(upload_folder(), idea.image_path)
        try:
            with open(path, "rb") as file:
                return small_jpeg(file.read()), None
        except OSError:
            current_app.logger.warning("Idea picture missing: %s", path)
    if idea.image_url:
        return None, idea.image_url
    raise AiError(_("This idea has no picture."))


def match_pin(idea, items, language="English"):
    """{"item_ids": [...], "missing": [...], "note": "..."} for this pin."""
    image_bytes, image_url = _picture(idea)
    usable = [item for item in items if not item.in_wash][:MAX_ITEMS]
    prompt = PROMPT.format(wardrobe=wardrobe_lines(usable), language=language)
    return ask_claude(prompt, _schema([item.id for item in usable]),
                      image_bytes=image_bytes, image_url=image_url, max_tokens=1024)
