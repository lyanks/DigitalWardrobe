import io
from datetime import date
from itertools import groupby

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import OWNED, WISHLIST, Category, Item
from app.services.images import InvalidImageError, delete_image, save_image
from app.services.product_page import FetchError, download_image
from app.services.stats import last_worn_date
from app.wardrobe.choices import COLORS, PRIORITIES, SEASONS
from app.wardrobe.forms import WISH_FIELDS, BoughtForm, DeleteForm, ItemForm

# url_prefix: every route below starts with /items.
bp = Blueprint("wardrobe", __name__, url_prefix="/items")


@bp.before_request
@login_required
def require_login():
    """Runs before every route in this blueprint: the whole wardrobe is private."""


def get_own_item_or_404(item_id):
    """Load an item only if it belongs to the logged-in user.

    Someone else's item answers 404 (not 403), so nobody can even find out
    which ids exist. Every route that touches one item goes through here.
    """
    item = db.session.scalar(
        db.select(Item).filter_by(id=item_id, user_id=current_user.id)
    )
    if item is None:
        abort(404)
    return item


def _category_choices():
    categories = db.session.scalars(db.select(Category).order_by(Category.id))
    return [(c.id, c.name) for c in categories]


# ---------- Read: list with filters and sorting ----------

# value in the URL -> label in the dropdown. "custom" (your own
# drag-and-drop order) is the default.
SORT_OPTIONS = {
    "custom": "My order",
    "newest": "Newest first",
    "oldest": "Oldest first",
    "name": "Name A–Z",
    "name_desc": "Name Z–A",
    "color": "Color",
    "category": "Category",
}


def _order_by(sort):
    """Translate a sort choice into ORDER BY columns."""
    if sort == "newest":
        return [Item.created_at.desc(), Item.id.desc()]
    if sort == "oldest":
        return [Item.created_at, Item.id]
    if sort == "name":
        return [db.func.lower(Item.name), Item.id]
    if sort == "name_desc":
        return [db.func.lower(Item.name).desc(), Item.id]
    if sort == "color":
        # Follow the order of the COLORS palette (black, white, grey, ...),
        # not the alphabet. CASE turns each color name into its index.
        palette_index = db.case(
            {name: index for index, name in enumerate(COLORS)},
            value=Item.color, else_=len(COLORS),
        )
        return [palette_index, db.func.lower(Item.name)]
    if sort == "category":
        return [Item.category_id, db.func.lower(Item.name)]
    return [Item.position, Item.id]  # "custom"

@bp.route("")
def index():
    # Query parameters: /items?category=2&color=blue&season=winter&q=jeans
    # request.args is a dict of everything after the "?".
    category_id = request.args.get("category", type=int)
    color = request.args.get("color", "")
    season = request.args.get("season", "")
    text = request.args.get("q", "").strip()
    sort = request.args.get("sort", "custom")
    if sort not in SORT_OPTIONS:
        sort = "custom"

    # Start with "all my items" and narrow it down one filter at a time.
    # Nothing is sent to the database until we ask for the results.
    query = Item.owned_by(current_user.id)
    if category_id:
        query = query.filter_by(category_id=category_id)
    if color in COLORS:
        query = query.filter_by(color=color)
    if season in SEASONS and season != "all":
        # An "all seasons" item also fits a winter search.
        query = query.where(Item.season.in_([season, "all"]))
    if text:
        pattern = f"%{text}%"  # % = "any characters" in SQL LIKE
        query = query.where(
            Item.name.ilike(pattern) | Item.brand.ilike(pattern) | Item.notes.ilike(pattern)
        )
    items = db.session.scalars(query.order_by(*_order_by(sort))).all()

    total = db.session.scalar(
        db.select(db.func.count()).select_from(Item.owned_by(current_user.id).subquery())
    )
    return render_template(
        "wardrobe/index.html", title="Wardrobe", items=items, total=total,
        categories=_category_choices(), colors=COLORS, seasons=SEASONS,
        filters={"category": category_id, "color": color, "season": season, "q": text},
        sort=sort, sort_options=SORT_OPTIONS,
    )


# ---------- Reorder (called by JavaScript, answers JSON) ----------

@bp.route("/reorder", methods=["POST"])
def reorder():
    """Save a new drag-and-drop order.

    The browser sends {"ids": [7, 3, 9]}: the cards it shows, in their new
    order. With filters on, that's only some of your items, so we reuse the
    position numbers those items already had and hand them out in the new
    order. Items you can't see keep their place.
    """
    data = request.get_json(silent=True) or {}
    ids = data.get("ids")
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids) \
            or len(ids) != len(set(ids)):
        return jsonify(error="Send a list of distinct item ids."), 400

    items = db.session.scalars(
        Item.owned_by(current_user.id).where(Item.id.in_(ids))
    ).all()
    if len(items) != len(ids):
        # Some id isn't yours (or doesn't exist): change nothing.
        return jsonify(error="Unknown item."), 404

    slots = sorted(item.position for item in items)
    if len(set(slots)) != len(slots):
        # Two items share a number: renumber everything 0, 1, 2... first.
        _renumber_positions()
        slots = sorted(item.position for item in items)

    by_id = {item.id: item for item in items}
    for item_id, slot in zip(ids, slots):
        by_id[item_id].position = slot
    db.session.commit()
    return jsonify(ok=True)


def _renumber_positions():
    mine = db.session.scalars(
        Item.owned_by(current_user.id).order_by(Item.position, Item.id)
    )
    for number, item in enumerate(mine):
        item.position = number


# ---------- Create ----------

@bp.route("/new", methods=["GET", "POST"])
def create():
    form = ItemForm()
    form.category_id.choices = _category_choices()
    del form.remove_photo  # nothing to remove on a new item
    _drop_fields(form, WISH_FIELDS)

    if form.validate_on_submit():
        item = Item(user_id=current_user.id, position=_first_position())
        if _fill_item_from_form(item, form):
            db.session.add(item)
            db.session.commit()
            flash(f"Added “{item.name}” to your wardrobe.", "success")
            return redirect(url_for("wardrobe.detail", item_id=item.id))

    return render_template("wardrobe/form.html", title="Add item", form=form, item=None)


def _first_position():
    """New clothes go first in "My order": one place before the current first."""
    first = db.session.scalar(
        db.select(db.func.min(Item.position)).filter_by(user_id=current_user.id)
    )
    return first - 1 if first is not None else 0


def _drop_fields(form, names):
    """Remove fields that don't apply, so they're neither shown nor validated."""
    for name in names:
        delattr(form, name)


# ---------- Wishlist ----------

@bp.route("/wishlist")
def wishlist():
    # Must-haves first. "priority IS NULL" is False (0) for wishes with a
    # priority and True (1) without, so wishes with no priority go last.
    wishes = db.session.scalars(
        Item.wished_by(current_user.id)
        .order_by(Item.priority.is_(None), Item.priority, Item.created_at.desc())
    ).all()
    # [("Must have", [wish, wish]), ("Someday", [wish]), ...]. groupby only
    # joins neighbours, which works because the list is already sorted.
    groups = [
        (PRIORITIES.get(priority, "No priority"), list(wishes_in_group))
        for priority, wishes_in_group in groupby(wishes, key=lambda wish: wish.priority)
    ]
    return render_template("wardrobe/wishlist.html", title="Wishlist", groups=groups)


@bp.route("/wishlist/new", methods=["GET", "POST"])
def create_wish():
    form = ItemForm()
    form.category_id.choices = _category_choices()
    _drop_fields(form, ("remove_photo", "purchase_date"))

    if form.validate_on_submit():
        item = Item(user_id=current_user.id, status=WISHLIST)
        if _fill_item_from_form(item, form):
            db.session.add(item)
            db.session.commit()
            flash(f"Added “{item.name}” to your wishlist.", "success")
            return redirect(url_for("wardrobe.detail", item_id=item.id))

    return render_template("wardrobe/form.html", title="Add a wish", form=form, item=None)


@bp.route("/<int:item_id>/bought", methods=["POST"])
def bought(item_id):
    """"I bought it": the wish becomes a piece of your wardrobe.

    Same row, only the status changes, so the photo, link and price stay.
    """
    item = get_own_item_or_404(item_id)
    if not item.is_wish:
        abort(400)
    if BoughtForm().validate_on_submit():
        item.status = OWNED
        item.purchase_date = date.today()
        item.priority = None
        item.position = _first_position()
        db.session.commit()
        flash(f"“{item.name}” is in your wardrobe now. Enjoy it!", "success")
    return redirect(url_for("wardrobe.detail", item_id=item.id))


# ---------- Read: one item ----------

@bp.route("/<int:item_id>")
def detail(item_id):
    item = get_own_item_or_404(item_id)
    return render_template(
        "wardrobe/detail.html", title=item.name, item=item, colors=COLORS,
        last_worn=None if item.is_wish else last_worn_date(item),
        priorities=PRIORITIES, bought_form=BoughtForm(),
    )


# ---------- Update ----------

@bp.route("/<int:item_id>/edit", methods=["GET", "POST"])
def edit(item_id):
    item = get_own_item_or_404(item_id)
    # obj=item pre-fills every field whose name matches an Item attribute.
    form = ItemForm(obj=item)
    form.category_id.choices = _category_choices()
    if not item.image_path:
        del form.remove_photo
    # A wish has a shop link and price but no "bought on" date yet.
    _drop_fields(form, ("purchase_date",) if item.is_wish else WISH_FIELDS)

    if form.validate_on_submit():
        if _fill_item_from_form(item, form):
            db.session.commit()
            flash("Changes saved.", "success")
            return redirect(url_for("wardrobe.detail", item_id=item.id))

    return render_template("wardrobe/form.html", title=f"Edit {item.name}", form=form, item=item)


# ---------- Delete (two steps) ----------

@bp.route("/<int:item_id>/delete", methods=["GET", "POST"])
def delete(item_id):
    item = get_own_item_or_404(item_id)
    form = DeleteForm()

    # GET only shows "Are you sure?". Nothing changes until the POST.
    if form.validate_on_submit():
        delete_image(item.image_path)
        db.session.delete(item)
        db.session.commit()
        flash(f"Deleted “{item.name}”.", "info")
        return redirect(url_for("wardrobe.wishlist" if item.is_wish else "wardrobe.index"))

    return render_template("wardrobe/delete.html", title="Delete item", item=item, form=form)


def _fill_item_from_form(item, form):
    """Copy the form into the item. Return False if the photo was invalid."""
    photo = form.photo.data
    if not photo and "image_url" in form and form.image_url.data:
        # Autofill found a photo on the shop's page: download it now and
        # treat it exactly like an upload (Pillow checks and shrinks it).
        try:
            # A filename is needed: an upload without one counts as "no file".
            photo = FileStorage(stream=io.BytesIO(download_image(form.image_url.data)),
                                filename="shop-photo")
        except FetchError as error:
            form.photo.errors.append(f"Couldn't get the shop's photo: {error}")
            return False
    if photo:
        try:
            new_path = save_image(photo, "items")
        except InvalidImageError as error:
            form.photo.errors.append(str(error))
            return False
        delete_image(item.image_path)
        item.image_path = new_path
    elif "remove_photo" in form and form.remove_photo.data:
        delete_image(item.image_path)
        item.image_path = None

    item.name = form.name.data.strip()
    item.category_id = form.category_id.data
    item.color = form.color.data
    item.season = form.season.data
    item.style = form.style.data or None
    item.brand = (form.brand.data or "").strip() or None
    item.size = (form.size.data or "").strip() or None
    item.notes = (form.notes.data or "").strip() or None
    # `"name" in form` is True only for fields the route didn't drop.
    if "purchase_date" in form:
        item.purchase_date = form.purchase_date.data
    if "shop_url" in form:
        item.shop_url = (form.shop_url.data or "").strip() or None
        item.price = form.price.data
        item.currency = form.currency.data
        item.priority = form.priority.data or None  # 0 ("—") means no priority
    return True
