"""Saving and deleting uploaded photos. Plain Python + Pillow, no routes.

Used by the avatar upload (auth) and the item photo upload (wardrobe),
so both follow exactly the same safety rules.
"""
import os
import uuid

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError


class InvalidImageError(ValueError):
    """The uploaded file is not an image Pillow can read."""


def save_image(file_storage, subfolder, max_size=1200):
    """Check, shrink and save an uploaded image. Return its relative path.

    - Pillow must be able to open it, so a renamed .exe is rejected even
      if its name ends in .png.
    - The photo is turned upright (phones store rotation separately),
      shrunk to at most max_size pixels per side, and saved as JPEG.
      Re-saving also drops hidden metadata like GPS location.
    - The file gets a random name; the uploaded name is never used.
    """
    try:
        image = Image.open(file_storage.stream)
        image = ImageOps.exif_transpose(image)
    except (UnidentifiedImageError, OSError) as error:
        raise InvalidImageError("That file is not a readable image.") from error

    image.thumbnail((max_size, max_size))  # keeps proportions, never enlarges
    if image.mode != "RGB":
        image = image.convert("RGB")  # JPEG has no transparency

    relative_path = f"{subfolder}/{uuid.uuid4().hex}.jpg"
    full_path = os.path.join(current_app.config["UPLOAD_FOLDER"], relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    image.save(full_path, "JPEG", quality=85)
    return relative_path


def delete_image(relative_path):
    """Delete a previously saved image. Missing files are ignored."""
    if not relative_path:
        return
    full_path = os.path.join(current_app.config["UPLOAD_FOLDER"], relative_path)
    if os.path.exists(full_path):
        os.remove(full_path)
