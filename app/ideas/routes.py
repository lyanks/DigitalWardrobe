"""Ideas: saved inspiration, mostly Pinterest pins.

Paste a pin link and the server reads the pin's picture and title
(services/pins.py), then keeps its own copy of the picture. Or upload a
picture (a screenshot works too). Outfits can say which idea they
recreate (the "Inspiration" choice on the outfit form).
"""
import io

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_babel import get_locale
from flask_babel import gettext as _
from flask_login import current_user, login_required
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.ideas.forms import DeleteIdeaForm, IdeaForm
from app.models import Idea, Item
from app.outfits.forms import SaveSuggestionForm
from app.services import ai
from app.services.outfit_board import place
from app.services.outfit_rules import outfit_problems, sort_by_slot
from app.services.pin_match import match_pin
from app.services.images import InvalidImageError, delete_image, save_image
from app.services.pins import fetch_pin
from app.services.product_page import FetchError, download_image

bp = Blueprint("ideas", __name__, url_prefix="/ideas")


@bp.before_request
@login_required
def require_login():
    """Your ideas are private."""


def get_own_idea_or_404(idea_id):
    idea = db.session.scalar(db.select(Idea).filter_by(id=idea_id, user_id=current_user.id))
    if idea is None:
        abort(404)
    return idea


def _copy_picture(image_url):
    """Download the pin's picture into uploads/ideas/. None if we can't.

    On PythonAnywhere's free plan the picture's site may not be on the
    allow-list. That's fine: the idea then shows the picture straight
    from the web (idea.image_url).
    """
    try:
        data = download_image(image_url)
        return save_image(FileStorage(stream=io.BytesIO(data), filename="pin"), "ideas")
    except (FetchError, InvalidImageError):
        return None


def _fill_idea(form, idea):
    """Copy the form into a new idea. Return False (with the error on the
    form) if neither the link nor the picture worked."""
    if form.photo.data:
        try:
            idea.image_path = save_image(form.photo.data, "ideas")
        except InvalidImageError as error:
            form.photo.errors.append(str(error))
            return False
    if form.link.data:
        idea.source_url = form.link.data.strip()
        if not idea.image_path:
            try:
                pin = fetch_pin(idea.source_url)
            except FetchError as error:
                form.link.errors.append(str(error))
                return False
            idea.title = pin["title"]
            idea.image_url = pin["image_url"]
            idea.image_path = _copy_picture(pin["image_url"])
    idea.note = (form.note.data or "").strip() or None
    return True


@bp.route("", methods=["GET", "POST"])
def index():
    """The board of ideas, with the "save an idea" form on top."""
    form = IdeaForm()
    if form.validate_on_submit():
        idea = Idea(user_id=current_user.id)
        if _fill_idea(form, idea):
            db.session.add(idea)
            db.session.commit()
            flash(_("Idea saved."), "success")
            return redirect(url_for("ideas.index"))
    return render_template("ideas/index.html", title=_("Ideas"), form=form, ideas=current_user.ideas,
                           ai_enabled=ai.is_enabled())


@bp.route("/<int:idea_id>/suggest", methods=["POST"])
def suggest(idea_id):
    """"Make it with my clothes": Claude picks pieces from your wardrobe.

    A POST, not a link: each press costs a little money and counts
    towards the daily AI limit (ai.use_quota).
    """
    idea = get_own_idea_or_404(idea_id)
    items = db.session.scalars(Item.owned_by(current_user.id)).all()
    if not items:
        flash(_("Add a few clothes first: at least a top and a bottom, or a dress."), "info")
        return redirect(url_for("ideas.index"))
    try:
        ai.use_quota(current_user.id)
        language = "Ukrainian" if str(get_locale()) == "uk" else "English"
        answer = match_pin(idea, items, language)
    except ai.AiError as error:
        flash(str(error), "error")
        return redirect(url_for("ideas.index"))

    # Trust, but check: only your own clothes, each once, head to toe.
    mine = {item.id: item for item in items}
    picked = sort_by_slot([mine[i] for i in dict.fromkeys(answer["item_ids"]) if i in mine])
    return render_template(
        "ideas/suggest.html", title=_("Make it with my clothes"), idea=idea, items=picked,
        pieces=[(item, place(item)) for item in picked], problems=outfit_problems(picked),
        note=answer["note"], missing=answer["missing"], form=SaveSuggestionForm(),
    )


@bp.route("/<int:idea_id>/delete", methods=["POST"])
def delete(idea_id):
    idea = get_own_idea_or_404(idea_id)
    if DeleteIdeaForm().validate_on_submit():
        delete_image(idea.image_path)
        db.session.delete(idea)  # outfits made after it stay
        db.session.commit()
        flash(_("Idea deleted."), "info")
    return redirect(url_for("ideas.index"))
