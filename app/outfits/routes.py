from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Category, Item, Outfit, OutfitItem
from app.outfits.forms import DeleteOutfitForm, OutfitForm
from app.services.images import InvalidImageError, delete_image, save_image
from app.services.outfit_rules import outfit_problems, sort_by_slot

bp = Blueprint("outfits", __name__, url_prefix="/outfits")


@bp.before_request
@login_required
def require_login():
    """Every outfit page is private."""


def get_own_outfit_or_404(outfit_id):
    """Same rule as items: someone else's outfit is simply "not found"."""
    outfit = db.session.scalar(
        db.select(Outfit).filter_by(id=outfit_id, user_id=current_user.id)
    )
    if outfit is None:
        abort(404)
    return outfit


def my_items_by_category():
    """[(category, [items...]), ...] for the builder, empty categories left out."""
    items = db.session.scalars(
        Item.owned_by(current_user.id)
        .join(Item.category).order_by(Category.id, Item.position, Item.id)
    ).all()
    groups = {}
    for item in items:
        groups.setdefault(item.category, []).append(item)
    return list(groups.items())


def _prepare_form(form):
    """Fill the item choices with the user's items; return the groups for the page."""
    groups = my_items_by_category()
    form.item_ids.choices = [(item.id, item.name) for _, items in groups for item in items]
    return groups


def _save_if_valid(form, outfit):
    """Validate the form and the outfit rules; save and return True if all is well."""
    if not form.validate_on_submit():
        return False

    # Only the user's items were allowed as choices, so this can't
    # load anyone else's clothes.
    items = db.session.scalars(
        Item.owned_by(current_user.id).where(Item.id.in_(form.item_ids.data))
    ).all()
    problems = outfit_problems(items)
    if problems:
        form.item_ids.errors.extend(problems)
        return False

    # The same photo handling as items, in its own folder: uploads/outfits/.
    if form.photo.data:
        try:
            new_path = save_image(form.photo.data, "outfits")
        except InvalidImageError as error:
            form.photo.errors.append(str(error))
            return False
        delete_image(outfit.image_path)
        outfit.image_path = new_path
    elif "remove_photo" in form and form.remove_photo.data:
        delete_image(outfit.image_path)
        outfit.image_path = None

    outfit.name = form.name.data.strip()
    outfit.occasion = form.occasion.data or None
    outfit.notes = (form.notes.data or "").strip() or None
    # Keep the links that already exist, add new ones for newly ticked
    # items. Links left out of the list are deleted (delete-orphan).
    existing = {link.item_id: link for link in outfit.item_links}
    outfit.item_links = [existing.get(item.id) or OutfitItem(item=item) for item in sort_by_slot(items)]
    for number, link in enumerate(outfit.item_links):
        link.position = number
    db.session.add(outfit)
    db.session.commit()
    return True


# ---------- Read: list ----------

@bp.route("")
def index():
    outfits = db.session.scalars(
        db.select(Outfit).filter_by(user_id=current_user.id).order_by(Outfit.created_at.desc(), Outfit.id.desc())
    ).all()
    return render_template("outfits/index.html", title="Outfits", outfits=outfits)


# ---------- Create ----------

@bp.route("/new", methods=["GET", "POST"])
def create():
    form = OutfitForm()
    del form.remove_photo  # nothing to remove on a new outfit
    groups = _prepare_form(form)
    outfit = Outfit(user_id=current_user.id)
    if _save_if_valid(form, outfit):
        flash(f"Saved the outfit “{outfit.name}”.", "success")
        return redirect(url_for("outfits.detail", outfit_id=outfit.id))
    return render_template("outfits/form.html", title="New outfit", form=form, groups=groups, outfit=None)


# ---------- Read: one outfit ----------

@bp.route("/<int:outfit_id>")
def detail(outfit_id):
    outfit = get_own_outfit_or_404(outfit_id)
    # Deleting an item can break an outfit (e.g. its only top is gone).
    # The outfit is kept, but we say what's missing.
    problems = outfit_problems(outfit.items) if outfit.items else ["All its items were deleted."]
    # For the one-line planner summary: how often worn, and the next planned day.
    today = date.today()
    worn_count = sum(1 for entry in outfit.schedule if entry.worn)
    next_entry = next((entry for entry in outfit.schedule if entry.date >= today), None)
    return render_template(
        "outfits/detail.html", title=outfit.name, outfit=outfit, problems=problems,
        worn_count=worn_count, next_entry=next_entry,
    )


# ---------- Update ----------

@bp.route("/<int:outfit_id>/edit", methods=["GET", "POST"])
def edit(outfit_id):
    outfit = get_own_outfit_or_404(outfit_id)
    form = OutfitForm(obj=outfit)
    if not outfit.image_path:
        del form.remove_photo
    groups = _prepare_form(form)
    if not form.is_submitted():
        # obj=outfit can't guess item_ids (the outfit has items, not ids).
        form.item_ids.data = [item.id for item in outfit.items]
    if _save_if_valid(form, outfit):
        flash("Outfit saved.", "success")
        return redirect(url_for("outfits.detail", outfit_id=outfit.id))
    return render_template("outfits/form.html", title=f"Edit {outfit.name}", form=form, groups=groups, outfit=outfit)


# ---------- Delete (two steps, like items) ----------

@bp.route("/<int:outfit_id>/delete", methods=["GET", "POST"])
def delete(outfit_id):
    outfit = get_own_outfit_or_404(outfit_id)
    form = DeleteOutfitForm()
    if form.validate_on_submit():
        delete_image(outfit.image_path)
        db.session.delete(outfit)  # its links go too; the items stay
        db.session.commit()
        flash(f"Deleted the outfit “{outfit.name}”. Your clothes are still in the wardrobe.", "info")
        return redirect(url_for("outfits.index"))
    return render_template("outfits/delete.html", title="Delete outfit", outfit=outfit, form=form)
