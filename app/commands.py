"""Commands you run in the terminal: `flask photos cut-out`, `flask goals`,
`flask invites create`.

@click.group() makes "photos" a group; each @photos.command() inside it
is one sub-command. Flask finds them because create_app() registers the
group with app.cli.add_command().

Nothing here is lost: the original photo is moved to uploads/items/originals/
and the cut-out PNG keeps the same random name, so `restore` can find it.
"""
import os

import click
from PIL import Image

from app.extensions import db
from app.goals import GOALS
from app.models import GoalAnswer, Item
from app.services.images import cut_out_white, write_image

ORIGINALS = "items/originals"


@click.group()
def photos():
    """Tidy up item photos."""


def _items(ids):
    """The items to work on: the given ids, or every item with a photo."""
    query = db.select(Item).where(Item.image_path.is_not(None)).order_by(Item.id)
    if ids:
        query = query.where(Item.id.in_(ids))
    return db.session.scalars(query).all()


def _full(relative_path):
    from flask import current_app
    return os.path.join(current_app.config["UPLOAD_FOLDER"], relative_path)


@photos.command("cut-out")
@click.argument("item_ids", nargs=-1, type=int)
def cut_out(item_ids):
    """Remove the white background from item photos.

    flask photos cut-out        every item photo
    flask photos cut-out 3 7    only items 3 and 7
    """
    done = 0
    for item in _items(item_ids):
        if not item.image_path.endswith(".jpg"):
            continue  # PNGs are already cut out (or came that way)
        path = _full(item.image_path)
        if not os.path.exists(path):
            click.echo(f"#{item.id} {item.name}: photo file missing, skipped")
            continue
        with Image.open(path) as image:
            cut = cut_out_white(image)
        if cut is None:
            click.echo(f"#{item.id} {item.name}: no white background found, kept")
            continue
        name = os.path.splitext(os.path.basename(item.image_path))[0]
        item.image_path = write_image(cut, "items", name=name)
        os.makedirs(_full(ORIGINALS), exist_ok=True)
        os.replace(path, _full(f"{ORIGINALS}/{name}.jpg"))
        done += 1
        click.echo(f"#{item.id} {item.name}: cut out")
    db.session.commit()
    click.echo(f"Done: {done} photo(s) changed. Originals are in uploads/{ORIGINALS}/.")


@photos.command()
@click.argument("item_ids", nargs=-1, type=int)
def restore(item_ids):
    """Put the original photos back (undo cut-out).

    flask photos restore 3      only item 3
    """
    done = 0
    for item in _items(item_ids):
        name, extension = os.path.splitext(os.path.basename(item.image_path))
        original = f"{ORIGINALS}/{name}.jpg"
        if extension != ".png" or not os.path.exists(_full(original)):
            continue
        os.remove(_full(item.image_path))
        os.replace(_full(original), _full(f"items/{name}.jpg"))
        item.image_path = f"items/{name}.jpg"
        done += 1
        click.echo(f"#{item.id} {item.name}: original back")
    db.session.commit()
    click.echo(f"Done: {done} photo(s) restored.")


@click.command()
def goals():
    """How many people picked each reason in the setup wizard."""
    counts = dict(db.session.execute(
        db.select(GoalAnswer.goal, db.func.count()).group_by(GoalAnswer.goal)
    ).all())
    for key, label in GOALS.items():
        click.echo(f"{counts.get(key, 0):>5}  {label}")


@click.group()
def invites():
    """Invite codes (the admin page at /admin/invites does the same)."""


@invites.command()
@click.option("--note", help="Who it's for.")
def create(note):
    """Make a new invite code and print it."""
    from app.invites import create_invite
    click.echo(create_invite(note).code)
