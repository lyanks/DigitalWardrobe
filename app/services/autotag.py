"""Guess an item's details from its photo, with Claude (see ai.py).

suggest_details(photo bytes) -> {"name": "Black leather bomber jacket",
"category_id": 4, "color": "black", "seasons": ["autumn", "winter"],
"styles": ["casual", "streetwear"], "moods": ["classy"], "brand": ""}

The model may only answer with words from our own lists (the categories,
colours, seasons, styles and moods the admin set up): they go into the
JSON schema as "enum", the list of allowed values. So every answer fits
straight into the form, and nothing new sneaks into the database.

Cost: the photo is shrunk to 512 px first, about 350 tokens. With the
instructions and lists that's ~900 tokens in and ~150 out: about $0.0002
per photo with Claude Haiku 5.5.
"""
import io

from PIL import Image, ImageOps

from app import options
from app.services.ai import ask_claude

# Big enough to see the fabric and a logo, small enough to be cheap.
AI_IMAGE_SIZE = 512
# Behind a cut-out: mid grey, so both black and white clothes stand out.
BACKDROP = (128, 128, 128)


def small_jpeg(image_bytes):
    """Any photo -> a small JPEG for the AI. A cut-out PNG gets a grey backdrop."""
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes)))
    image.thumbnail((AI_IMAGE_SIZE, AI_IMAGE_SIZE))
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        backdrop = Image.new("RGB", image.size, BACKDROP)
        backdrop.paste(image, mask=image.getchannel("A"))
        image = backdrop
    out = io.BytesIO()
    image.convert("RGB").save(out, "JPEG", quality=80)
    return out.getvalue()


def _schema(categories, colors, seasons, styles, moods):
    def many(values):
        return {"type": "array", "items": {"type": "string", "enum": values}}
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "category": {"type": "string", "enum": categories},
            "color": {"type": "string", "enum": colors},
            "seasons": many(seasons),
            "styles": many(styles),
            "moods": many(moods),
            "brand": {"type": "string"},
        },
        "required": ["name", "category", "color", "seasons", "styles", "moods", "brand"],
        "additionalProperties": False,
    }


PROMPT = """This is a photo of one piece of clothing (or shoes, or an accessory) \
someone is adding to their digital wardrobe. Fill in its details.

- name: a short everyday name, 2 to 5 words, in English, like "Black leather bomber jacket". \
Mention the material when you can see it.
- category, color: the best fit from the lists. "multicolor" only for clear patterns of several colours.
- seasons: when it is comfortable to wear. Leave the list empty if it suits all year.
- styles: 1 to 3 that describe how it looks.
- moods: 1 or 2. home = for staying in, comfortable = easy everyday, \
classy = put-together, elegant = dressy, for evenings and events.
- brand: only if a logo or label is clearly readable, else "".
If the photo shows no clothing, still answer with your best guess and the name "Unknown item"."""


def suggest_details(image_bytes):
    categories = {category.name: category.id for category in options.categories()}
    seasons = [value for value in options.values("season") if value != "all"]
    schema = _schema(list(categories), options.values("color"), seasons,
                     options.values("style"), options.values("mood"))
    answer = ask_claude(PROMPT, schema, image_bytes=small_jpeg(image_bytes))
    answer["category_id"] = categories.get(answer.pop("category", None))
    answer["name"] = (answer.get("name") or "").strip()[:100]
    answer["brand"] = (answer.get("brand") or "").strip()[:60]
    return answer
