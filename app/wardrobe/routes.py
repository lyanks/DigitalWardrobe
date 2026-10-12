from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Category, Item
from app.services.images import InvalidImageError, delete_image, save_image
from app.wardrobe.choices import COLORS, SEASONS
from app.wardrobe.forms import DeleteForm, ItemForm

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


# ---------- Read: list with filters ----------

@bp.route("")
def index():
    # Query parameters: /items?category=2&color=blue&season=winter&q=jeans
    # request.args is a dict of everything after the "?".
    category_id = request.args.get("category", type=int)
    color = request.args.get("color", "")
    season = request.args.get("season", "")
    text = request.args.get("q", "").strip()

    # Start with "all my items" and narrow it down one filter at a time.
    # Nothing is sent to the database until we ask for the results.
    query = db.select(Item).filter_by(user_id=current_user.id)
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
    items = db.session.scalars(query.order_by(Item.created_at.desc())).all()

    total = db.session.scalar(
        db.select(db.func.count(Item.id)).filter_by(user_id=current_user.id)
    )
    return render_template(
        "wardrobe/index.html", title="Wardrobe", items=items, total=total,
        categories=_category_choices(), colors=COLORS, seasons=SEASONS,
        filters={"category": category_id, "color": color, "season": season, "q": text},
    )


# ---------- Create ----------

@bp.route("/new", methods=["GET", "POST"])
def create():
    form = ItemForm()
    form.category_id.choices = _category_choices()
    del form.remove_photo  # nothing to remove on a new item

    if form.validate_on_submit():
        item = Item(user_id=current_user.id)
        if _fill_item_from_form(item, form):
            db.session.add(item)
            db.session.commit()
            flash(f"Added “{item.name}” to your wardrobe.", "success")
            return redirect(url_for("wardrobe.detail", item_id=item.id))

    return render_template("wardrobe/form.html", title="Add item", form=form, item=None)


# ---------- Read: one item ----------

@bp.route("/<int:item_id>")
def detail(item_id):
    item = get_own_item_or_404(item_id)
    return render_template(
        "wardrobe/detail.html", title=item.name, item=item, colors=COLORS,
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
        return redirect(url_for("wardrobe.index"))

    return render_template("wardrobe/delete.html", title="Delete item", item=item, form=form)


def _fill_item_from_form(item, form):
    """Copy the form into the item. Return False if the photo was invalid."""
    if form.photo.data:
        try:
            new_path = save_image(form.photo.data, "items")
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
    item.purchase_date = form.purchase_date.data
    item.notes = (form.notes.data or "").strip() or None
    return True
