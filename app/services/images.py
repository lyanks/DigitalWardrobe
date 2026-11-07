"""Saving and deleting uploaded photos. Plain Python + Pillow, no routes.

Used by the avatar upload (auth) and the item photo upload (wardrobe),
so both follow exactly the same safety rules.
"""
import os
import uuid

from flask_babel import gettext as _
from PIL import Image, ImageChops, ImageFilter, ImageOps, UnidentifiedImageError

# How far (0-255, per colour channel) a pixel may be from the background
# colour and still count as background. Bigger = cuts more, also shadows.
BACKGROUND_TOLERANCE = 40
# The search runs on a copy this many pixels wide/high, then the result is
# stretched back to full size. 500 is plenty for a clean edge and keeps it
# well under a second, even on PythonAnywhere's slow free CPU.
WORK_SIZE = 500
# At least this share of the photo's border must be the background colour,
# otherwise the background is too busy (a room, a street) to cut this way.
PLAIN_EDGE_SHARE = 0.6


class InvalidImageError(ValueError):
    """The uploaded file is not an image Pillow can read."""


def upload_folder():
    """The real uploads folder, or a guest's own folder (app/guests.py)."""
    from app.guests import upload_folder as folder
    return folder()


def _check_guest_limit():
    from app.guests import MAX_PHOTOS, is_guest, photo_count
    if is_guest() and photo_count() >= MAX_PHOTOS:
        raise InvalidImageError(_("Guests can add up to %(num)d photos.", num=MAX_PHOTOS))


def background_colour(edge_pixels):
    """Guess the background colour from the pixels along the photo's border.

    The median ("the middle value once sorted") of each channel ignores
    the few border pixels the garment covers, as long as most of the
    border is background.
    """
    def middle(values):
        return sorted(values)[len(values) // 2]
    return tuple(middle([pixel[channel] for pixel in edge_pixels]) for channel in range(3))


def cut_out_background(image, tolerance=BACKGROUND_TOLERANCE):
    """Make a plain background see-through. Return an RGBA image, or None.

    Works for any plain colour: white, a grey floor, a beige bedsheet.
    1. Look at the border of the photo and pick its most typical colour.
    2. "Flood fill" (the paint bucket in a drawing program): start at every
       border pixel of that colour and spread to neighbours of the same
       colour. It stops at the garment's outline, so the same colour
       *inside* the garment (a logo, a stripe) stays: the bucket can't
       reach it from the edge.
    3. Everything the bucket reached becomes see-through.

    None means "leave the photo as it is": the border isn't one plain
    colour (a busy background, use the AI button in the browser instead),
    or the bucket ate almost everything (a white shirt on white).
    """
    rgb = image.convert("RGB")
    small = rgb.copy()
    small.thumbnail((WORK_SIZE, WORK_SIZE))
    width, height = small.size
    pixels = list(small.get_flattened_data())  # one long list, row after row

    border = ([(x, 0) for x in range(width)] + [(x, height - 1) for x in range(width)]
              + [(0, y) for y in range(height)] + [(width - 1, y) for y in range(height)])
    colour = background_colour([pixels[y * width + x] for x, y in border])

    def is_background(pixel):
        return all(abs(pixel[channel] - colour[channel]) <= tolerance for channel in range(3))

    starts = [y * width + x for x, y in border if is_background(pixels[y * width + x])]
    if len(starts) < PLAIN_EDGE_SHARE * len(border):
        return None

    # The bucket: a "to do" list of pixels (by their index in the long list).
    # Each one we take off, we look at its 4 neighbours and add those that
    # are background and not seen yet. This is breadth-first search.
    seen = bytearray(width * height)  # 0 = garment, 255 = background
    for index in starts:
        seen[index] = 255
    todo = starts
    while todo:
        next_todo = []
        for index in todo:
            x, y = index % width, index // width
            neighbours = []
            if x > 0: neighbours.append(index - 1)
            if x < width - 1: neighbours.append(index + 1)
            if y > 0: neighbours.append(index - width)
            if y < height - 1: neighbours.append(index + width)
            for other in neighbours:
                if not seen[other] and is_background(pixels[other]):
                    seen[other] = 255
                    next_todo.append(other)
        todo = next_todo

    share = seen.count(255) / len(seen)
    if share > 0.95:
        return None

    # Turn the list back into a small black-and-white picture, stretch it
    # to the photo's size (BILINEAR gives a soft edge, not stairs), and flip
    # it: alpha (see-through-ness) is 0 for background, 255 for the garment.
    mask = Image.frombytes("L", (width, height), bytes(seen)).resize(rgb.size, Image.Resampling.BILINEAR)
    # MinFilter trims a 1-pixel fringe of background colour off the edge,
    # the blur softens it.
    alpha = ImageChops.invert(mask).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1))
    cut = image.convert("RGBA")
    cut.putalpha(alpha)
    return cut


def save_image(file_storage, subfolder, max_size=1200, remove_background=False):
    """Check, shrink and save an uploaded image. Return its relative path.

    - Pillow must be able to open it, so a renamed .exe is rejected even
      if its name ends in .png.
    - The photo is turned upright (phones store rotation separately),
      shrunk to at most max_size pixels per side, and saved as JPEG.
      Re-saving also drops hidden metadata like GPS location.
    - remove_background=True cuts out a plain background (see above).
      Then it's saved as PNG instead, because JPEG can't be see-through.
    - The file gets a random name; the uploaded name is never used.
    """
    _check_guest_limit()
    try:
        image = Image.open(file_storage.stream)
        image = ImageOps.exif_transpose(image)
    except (UnidentifiedImageError, OSError) as error:
        raise InvalidImageError(_("That file is not a readable image.")) from error

    image.thumbnail((max_size, max_size))  # keeps proportions, never enlarges
    if _has_see_through_parts(image):
        # Already cut out (a PNG with transparency): keep it that way.
        return write_image(image.convert("RGBA"), subfolder)
    cut = cut_out_background(image) if remove_background else None
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
    full_path = os.path.join(upload_folder(), relative_path)
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
    full_path = os.path.join(upload_folder(), relative_path)
    if os.path.exists(full_path):
        os.remove(full_path)
