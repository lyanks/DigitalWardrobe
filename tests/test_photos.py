"""Cutting the white background out of item photos."""
import io
import os

from PIL import Image, ImageDraw

from app.extensions import db
from app.services.images import cut_out_white
from tests.conftest import register
from tests.test_items import add_item, get_item


def product_photo():
    """A blue "shirt" on white, with a white logo inside the shirt."""
    image = Image.new("RGB", (100, 100), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((25, 25, 75, 75), fill=(40, 80, 200))
    draw.rectangle((45, 45, 55, 55), fill="white")  # the logo
    return image


def upload(image, name="shirt.png", mode="PNG"):
    buffer = io.BytesIO()
    image.save(buffer, mode)
    buffer.seek(0)
    return buffer, name


# ---------- the cut-out itself ----------

def test_white_background_becomes_see_through():
    cut = cut_out_white(product_photo())
    alpha = cut.getchannel("A")
    assert alpha.getpixel((2, 2)) == 0        # background: gone
    assert alpha.getpixel((35, 35)) == 255    # the shirt: kept
    assert alpha.getpixel((50, 50)) == 255    # white logo inside: kept


def test_nothing_to_cut_returns_none():
    assert cut_out_white(Image.new("RGB", (50, 50), "red")) is None    # no white edge
    assert cut_out_white(Image.new("RGB", (50, 50), "white")) is None  # all white


# ---------- uploads ----------

def test_upload_cuts_out_white_by_default(client, app):
    register(client)
    page = client.get("/items/new").get_data(as_text=True)
    assert '<input checked id="remove_white"' in page  # ticked on a new item
    add_item(client, name="Shirt", photo=upload(product_photo()), remove_white="y")
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
    assert "Shirt: cut out" in result.output and "Red: no white background found" in result.output
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
