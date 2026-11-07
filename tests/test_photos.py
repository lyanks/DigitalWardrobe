"""Cutting a plain background out of item photos."""
import io
import os

import random

from PIL import Image, ImageDraw

from app.extensions import db
from app.services.images import cut_out_background
from tests.conftest import register
from tests.test_items import add_item, get_item


def product_photo(background="white"):
    """A blue "shirt" on a plain background, with a logo of the same
    colour as the background inside the shirt."""
    image = Image.new("RGB", (100, 100), background)
    draw = ImageDraw.Draw(image)
    draw.rectangle((25, 25, 75, 75), fill=(40, 80, 200))
    draw.rectangle((45, 45, 55, 55), fill=background)  # the logo
    return image


def upload(image, name="shirt.png", mode="PNG"):
    buffer = io.BytesIO()
    image.save(buffer, mode)
    buffer.seek(0)
    return buffer, name


# ---------- the cut-out itself ----------

def test_white_background_becomes_see_through():
    cut = cut_out_background(product_photo())
    alpha = cut.getchannel("A")
    assert alpha.getpixel((2, 2)) == 0        # background: gone
    assert alpha.getpixel((35, 35)) == 255    # the shirt: kept
    assert alpha.getpixel((50, 50)) == 255    # white logo inside: kept


def test_any_plain_colour_is_cut_out():
    for background in [(128, 128, 128), (225, 205, 170), (30, 30, 30)]:  # grey, beige, black
        alpha = cut_out_background(product_photo(background)).getchannel("A")
        assert alpha.getpixel((2, 2)) == 0 and alpha.getpixel((35, 35)) == 255, background


def test_a_slightly_uneven_background_still_counts_as_plain():
    """Real photos are never one exact colour: a bit of noise is fine."""
    noise = random.Random(1)
    image = product_photo((200, 190, 180))
    for x in range(100):
        for y in range(100):
            if not (25 <= x <= 75 and 25 <= y <= 75):
                image.putpixel((x, y), tuple(value + noise.randint(-15, 15) for value in (200, 190, 180)))
    alpha = cut_out_background(image).getchannel("A")
    assert alpha.getpixel((2, 2)) == 0 and alpha.getpixel((35, 35)) == 255


def test_the_garment_touching_the_edge_is_fine():
    image = Image.new("RGB", (100, 100), "white")
    ImageDraw.Draw(image).rectangle((30, 20, 70, 99), fill="black")  # trousers off the bottom
    alpha = cut_out_background(image).getchannel("A")
    assert alpha.getpixel((5, 5)) == 0 and alpha.getpixel((50, 95)) == 255


def test_nothing_to_cut_returns_none():
    assert cut_out_background(Image.new("RGB", (50, 50), "white")) is None  # all background
    busy = Image.new("RGB", (60, 60))
    noise = random.Random(2)
    busy.putdata([tuple(noise.randrange(256) for _ in range(3)) for _ in range(60 * 60)])
    assert cut_out_background(busy) is None  # no plain border: leave it to the AI button


# ---------- uploads ----------

def test_upload_cuts_out_a_plain_background_by_default(client, app):
    register(client)
    page = client.get("/items/new").get_data(as_text=True)
    assert '<input checked id="remove_background"' in page  # ticked on a new item
    assert "data-cutout" in page  # the "Cut out with AI" box
    add_item(client, name="Shirt", photo=upload(product_photo("grey")), remove_background="y")
    path = get_item("Shirt").image_path
    assert path.endswith(".png")
    with Image.open(os.path.join(app.config["UPLOAD_FOLDER"], path)) as saved:
        assert saved.mode == "RGBA"


def test_unticked_keeps_the_photo_as_it_is(client):
    register(client)
    add_item(client, name="White shirt", photo=upload(product_photo()))  # box not sent = unticked
    assert get_item("White shirt").image_path.endswith(".jpg")


def test_a_transparent_png_stays_transparent(client):
    register(client)
    image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((10, 10, 30, 30), fill=(200, 30, 30, 255))
    add_item(client, name="Cut already", photo=upload(image))
    assert get_item("Cut already").image_path.endswith(".png")


# ---------- flask photos cut-out / restore ----------

def test_cut_out_command_and_restore(client, app):
    register(client)
    add_item(client, name="Shirt", photo=upload(product_photo(), "shirt.jpg", "JPEG"))
    add_item(client, name="Red", photo=upload(Image.new("RGB", (40, 40), "red")))
    old = get_item("Shirt").image_path
    folder = app.config["UPLOAD_FOLDER"]
    runner = app.test_cli_runner()

    result = runner.invoke(args=["photos", "cut-out"])
    assert "Shirt: cut out" in result.output and "Red: no plain background found" in result.output
    db.session.expire_all()
    new = get_item("Shirt").image_path
    assert new.endswith(".png") and os.path.exists(os.path.join(folder, new))
    original = os.path.join(folder, "items/originals", os.path.basename(old))
    assert os.path.exists(original) and not os.path.exists(os.path.join(folder, old))

    result = runner.invoke(args=["photos", "restore"])
    assert "Shirt: original back" in result.output
    db.session.expire_all()
    assert get_item("Shirt").image_path == old
    assert os.path.exists(os.path.join(folder, old)) and not os.path.exists(os.path.join(folder, new))
