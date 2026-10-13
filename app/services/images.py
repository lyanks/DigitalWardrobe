"""Saving and deleting uploaded photos. Plain Python + Pillow, no routes.

Used by the avatar upload (auth) and the item photo upload (wardrobe),
so both follow exactly the same safety rules.
"""
import os
import uuid

from flask import current_app
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, UnidentifiedImageError

# How close to pure white (255) a pixel must be to count as background.
WHITE_TOLERANCE = 24


class InvalidImageError(ValueError):
    """The uploaded file is not an image Pillow can read."""


def cut_out_white(image, tolerance=WHITE_TOLERANCE):
    """Make a white background see-through. Return an RGBA image, or None.

    Product photos are usually a garment on plain white. A "flood fill"
    (the paint bucket in a drawing program) starts at the edges of the
    photo and spreads over every connected near-white pixel. It stops at
    the garment's outline, so white *inside* the garment (a logo, a white
    stripe) stays, because the bucket can't reach it from the edge.

    None means "leave the photo as it is": nothing white touched the edge,
    or the bucket ate almost everything (a white shirt on white).
    """
    rgb = image.convert("RGB")
    width, height = rgb.size
    filled = rgb.copy()
    marker = (255, 0, 255)  # pink: a colour a near-white pixel can't be

    def is_white(pixel):
        return min(pixel) >= 255 - tolerance

    # Start the bucket every few pixels along all four edges.
    edge = ([(x, 0) for x in range(0, width, 6)] + [(x, height - 1) for x in range(0, width, 6)]
            + [(0, y) for y in range(0, height, 6)] + [(width - 1, y) for y in range(0, height, 6)])
    for point in edge:
        if is_white(filled.getpixel(point)):
            ImageDraw.floodfill(filled, point, marker, thresh=tolerance)

    # Background = every pixel the bucket changed. ImageChops.difference
    # compares the two images; "L" turns it into one grey channel.
    changed = ImageChops.difference(rgb, filled).convert("L").point(lambda v: 255 if v else 0)
    share = changed.histogram()[255] / (width * height)
    if share == 0 or share > 0.95:
        return None

    # Alpha (see-through-ness): 0 = background, 255 = garment. MinFilter
    # trims a 1-pixel white fringe off the edge, the blur softens it.
    alpha = ImageChops.invert(changed).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1))
    cut = image.convert("RGBA")
    cut.putalpha(alpha)
    return cut


def save_image(file_storage, subfolder, max_size=1200, remove_white=False):
    """Check, shrink and save an uploaded image. Return its relative path.

    - Pillow must be able to open it, so a renamed .exe is rejected even
      if its name ends in .png.
    - The photo is turned upright (phones store rotation separately),
      shrunk to at most max_size pixels per side, and saved as JPEG.
      Re-saving also drops hidden metadata like GPS location.
    - remove_white=True cuts out a plain white background (see above).
      Then it's saved as PNG instead, because JPEG can't be see-through.
    - The file gets a random name; the uploaded name is never used.
    """
    try:
        image = Image.open(file_storage.stream)
        image = ImageOps.exif_transpose(image)
    except (UnidentifiedImageError, OSError) as error:
        raise InvalidImageError("That file is not a readable image.") from error

    image.thumbnail((max_size, max_size))  # keeps proportions, never enlarges
    if _has_see_through_parts(image):
        # Already cut out (a PNG with transparency): keep it that way.
        return write_image(image.convert("RGBA"), subfolder)
    cut = cut_out_white(image) if remove_white else None
    return write_image(cut, subfolder) if cut else write_image(image.convert("RGB"), subfolder)


def _has_see_through_parts(image):
    """True if any pixel of the image is (partly) transparent."""
    if image.mode not in ("RGBA", "LA", "P"):
        return False
    alpha = image.convert("RGBA").getchannel("A")
    return alpha.getextrema()[0] < 255  # the smallest alpha value


def write_image(image, subfolder, name=None):
    """Save under a random name (or `name`): PNG if it has see-through
    parts, else JPEG. Return the path relative to the uploads folder."""
    see_through = image.mode == "RGBA"
    extension = "png" if see_through else "jpg"
    relative_path = f"{subfolder}/{name or uuid.uuid4().hex}.{extension}"
    full_path = os.path.join(current_app.config["UPLOAD_FOLDER"], relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    if see_through:
        image.save(full_path, "PNG", optimize=True)
    else:
        image.save(full_path, "JPEG", quality=85)
    return relative_path


def delete_image(relative_path):
    """Delete a previously saved image. Missing files are ignored."""
    if not relative_path:
        return
    full_path = os.path.join(current_app.config["UPLOAD_FOLDER"], relative_path)
    if os.path.exists(full_path):
        os.remove(full_path)
