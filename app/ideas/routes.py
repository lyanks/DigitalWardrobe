"""Ideas: saved inspiration, mostly Pinterest pins.

Paste a pin link and the server reads the pin's picture and title
(services/pins.py), then keeps its own copy of the picture. Or upload a
picture (a screenshot works too). Outfits can say which idea they
recreate (the "Inspiration" choice on the outfit form).
"""
import io

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.ideas.forms import DeleteIdeaForm, IdeaForm
from app.models import Idea
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
    return render_template("ideas/index.html", title=_("Ideas"), form=form, ideas=current_user.ideas)


@bp.route("/<int:idea_id>/delete", methods=["POST"])
def delete(idea_id):
    idea = get_own_idea_or_404(idea_id)
    if DeleteIdeaForm().validate_on_submit():
        delete_image(idea.image_path)
        db.session.delete(idea)  # outfits made after it stay
        db.session.commit()
        flash(_("Idea deleted."), "info")
    return redirect(url_for("ideas.index"))
