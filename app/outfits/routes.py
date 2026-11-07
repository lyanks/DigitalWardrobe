from datetime import date, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app import options
from app.extensions import db
from app.models import Category, Item, Outfit, OutfitItem, SuggestionVote, WearLog, utcnow
from app.outfits.forms import DeleteOutfitForm, OutfitForm, SaveSuggestionForm, VoteForm
from app.services.combo_check import WINDOW_DAYS, worn_between
from app.services.images import InvalidImageError, delete_image, save_image
from app.services.outfit_board import apply_layout, editor_spots, parse_layout, place
from app.services.outfit_rules import outfit_problems, sort_by_slot
from app.services.suggest import season_of, suggest

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
        .join(Item.category).order_by(Category.position, Category.id, Item.position, Item.id)
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


def _render_form(title, form, groups, outfit):
    """The outfit form page, with every item's place on the board."""
    items = [item for _, items in groups for item in items]
    # After a form error, keep the pieces where you had just put them.
    sent = parse_layout(form.layout.data, {item.id for item in items}) if form.is_submitted() else None
    spots, defaults = editor_spots(items, outfit.item_links if outfit else [], sent)
    return render_template("outfits/form.html", title=title, form=form, groups=groups, outfit=outfit,
                           spots=spots, defaults=defaults, ideas=current_user.ideas)


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
    # Only one of your own ideas; anything else (0, someone else's) = none.
    my_ideas = {idea.id for idea in current_user.ideas}
    outfit.idea_id = form.idea_id.data if form.idea_id.data in my_ideas else None
    # Keep the links that already exist, add new ones for newly ticked
    # items. Links left out of the list are deleted (delete-orphan).
    existing = {link.item_id: link for link in outfit.item_links}
    outfit.item_links = [existing.get(item.id) or OutfitItem(item=item) for item in sort_by_slot(items)]
    for number, link in enumerate(outfit.item_links):
        link.position = number
    # Where each piece sits on the board (sent by outfit_board.js).
    apply_layout(outfit.item_links, parse_layout(form.layout.data, {item.id for item in items}))
    db.session.add(outfit)
    db.session.commit()
    return True


# ---------- Read: list ----------

@bp.route("")
def index():
    outfits = db.session.scalars(
        db.select(Outfit).filter_by(user_id=current_user.id).order_by(Outfit.created_at.desc(), Outfit.id.desc())
    ).all()
    return render_template("outfits/index.html", title=_("Outfits"), outfits=outfits)


# ---------- Create ----------

@bp.route("/new", methods=["GET", "POST"])
def create():
    form = OutfitForm()
    del form.remove_photo  # nothing to remove on a new outfit
    groups = _prepare_form(form)
    outfit = Outfit(user_id=current_user.id)
    if _save_if_valid(form, outfit):
        flash(_("Saved the outfit “%(name)s”.", name=outfit.name), "success")
        return redirect(url_for("outfits.detail", outfit_id=outfit.id))
    return _render_form(_("New outfit"), form, groups, None)


# ---------- Suggest a look (services/suggest.py) ----------

# How far back "Wear it" and "Not for me" still count.
VOTE_MEMORY_DAYS = 120


def _number(name, low, high):
    """A number from the address (?temp=9.5), or None if missing or silly."""
    try:
        value = float(request.args.get(name, ""))
    except ValueError:
        return None
    return value if low <= value <= high else None


def my_votes():
    since = utcnow() - timedelta(days=VOTE_MEMORY_DAYS)
    rows = db.session.scalars(
        db.select(SuggestionVote).where(SuggestionVote.user_id == current_user.id,
                                        SuggestionVote.created_at >= since)
    ).all()
    return [(row.id_set, row.liked) for row in rows]


def items_from_ids(text):
    """"3,7,12" -> your own items with those ids. Anyone else's aren't found."""
    wanted = {int(part) for part in (text or "").split(",") if part.strip().isdigit()}
    return db.session.scalars(Item.owned_by(current_user.id).where(Item.id.in_(wanted))).all()


@bp.route("/suggest")
def suggest_look():
    """Three looks from your own clothes.

    ?season=winter&mood=classy&mood=home, plus ?temp=9&rain=70 when the
    browser found today's weather (static/js/weather.js).
    """
    seasons = [value for value in options.values("season") if value != "all"]
    moods = options.values("mood")
    season = request.args.get("season")
    if season not in seasons:
        season = season_of(date.today())
    picked_moods = [mood for mood in request.args.getlist("mood") if mood in moods]
    temp = _number("temp", -60, 60)
    weather = None if temp is None else {"temp": temp, "rain": _number("rain", 0, 100) or 0}

    items = db.session.scalars(Item.owned_by(current_user.id)).all()
    today = date.today()
    recent = worn_between(current_user.id, today - timedelta(days=WINDOW_DAYS), today - timedelta(days=1))
    looks = suggest(items, season, picked_moods, current_user.undertone, current_user.body_shape,
                    recent.values(), weather=weather, votes=my_votes())
    # Each look as a board, with every piece in its usual spot.
    boards = [[(item, place(item)) for item in look.items] for look in looks]
    return render_template(
        "outfits/suggest.html", title=_("Suggest a look"), looks=list(zip(looks, boards)),
        seasons=seasons, season=season, moods=moods, picked_moods=picked_moods,
        form=SaveSuggestionForm(), vote_form=VoteForm(), weather=weather,
        item_count=len(items), back=request.full_path,
    )


@bp.route("/suggest/save", methods=["POST"])
def save_suggestion():
    form = SaveSuggestionForm()
    if form.validate_on_submit():
        items = items_from_ids(form.item_ids.data)
        if items and not outfit_problems(items):
            # Made from one of your pins? Only your own ideas count.
            my_ideas = {idea.id for idea in current_user.ideas}
            idea_id = int(form.idea_id.data) if (form.idea_id.data or "").isdigit() else None
            outfit = Outfit(user_id=current_user.id, name=form.name.data,
                            idea_id=idea_id if idea_id in my_ideas else None)
            outfit.item_links = [OutfitItem(item=item, position=number)
                                 for number, item in enumerate(sort_by_slot(items))]
            SuggestionVote.add(current_user.id, items, liked=True)
            db.session.add(outfit)
            db.session.commit()
            flash(_("Saved the outfit “%(name)s”.", name=outfit.name), "success")
            return redirect(url_for("outfits.detail", outfit_id=outfit.id))
    flash(_("That look couldn't be saved. Try another one."), "error")
    return redirect(url_for("outfits.suggest_look"))


def _back(form):
    """Back to the suggestions you were looking at, never to another site."""
    back = form.back.data or ""
    return back if back.startswith("/outfits/suggest") else url_for("outfits.suggest_look")


@bp.route("/suggest/wear", methods=["POST"])
def wear_suggestion():
    """"Wear it": log the look as worn today, and remember that you liked it."""
    form = VoteForm()
    items = items_from_ids(form.item_ids.data) if form.validate_on_submit() else []
    if items and not outfit_problems(items):
        WearLog.record(current_user.id, date.today(), sort_by_slot(items))
        SuggestionVote.add(current_user.id, items, liked=True)
        db.session.commit()
        flash(_("Logged as worn today. Suggestions will remember you liked it."), "success")
        return redirect(url_for("planner.log_look"))
    return redirect(_back(form))


@bp.route("/suggest/skip", methods=["POST"])
def skip_suggestion():
    """"Not for me": this look (and looks like it) move down from now on."""
    form = VoteForm()
    items = items_from_ids(form.item_ids.data) if form.validate_on_submit() else []
    if items:
        SuggestionVote.add(current_user.id, items, liked=False)
        db.session.commit()
        flash(_("Got it. You'll see fewer looks like that."), "info")
    return redirect(_back(form))


# ---------- Read: one outfit ----------

@bp.route("/<int:outfit_id>")
def detail(outfit_id):
    outfit = get_own_outfit_or_404(outfit_id)
    # Deleting an item can break an outfit (e.g. its only top is gone).
    # The outfit is kept, but we say what's missing.
    problems = outfit_problems(outfit.items) if outfit.items else [_("All its items were deleted.")]
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
        flash(_("Outfit saved."), "success")
        return redirect(url_for("outfits.detail", outfit_id=outfit.id))
    return _render_form(_("Edit %(name)s", name=outfit.name), form, groups, outfit)


# ---------- Delete (two steps, like items) ----------

@bp.route("/<int:outfit_id>/delete", methods=["GET", "POST"])
def delete(outfit_id):
    outfit = get_own_outfit_or_404(outfit_id)
    form = DeleteOutfitForm()
    if form.validate_on_submit():
        delete_image(outfit.image_path)
        db.session.delete(outfit)  # its links go too; the items stay
        db.session.commit()
        flash(_("Deleted the outfit “%(name)s”. Your clothes are still in the wardrobe.", name=outfit.name), "info")
        return redirect(url_for("outfits.index"))
    return render_template("outfits/delete.html", title=_("Delete outfit"), outfit=outfit, form=form)
