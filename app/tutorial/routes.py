"""The tutorial: one page that shows the main features of the app.

New users see a "New here?" banner on the home page until they open the
tutorial or close the banner. Either one fills in User.tutorial_seen_at,
so the banner never comes back. The page itself stays open to everyone,
visitors included (the landing page links to it).
"""
from flask import Blueprint, redirect, render_template, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app.extensions import db
from app.models import utcnow

bp = Blueprint("tutorial", __name__, url_prefix="/tutorial")


def mark_seen():
    if current_user.is_authenticated and current_user.tutorial_seen_at is None:
        current_user.tutorial_seen_at = utcnow()
        db.session.commit()


@bp.route("")
def index():
    mark_seen()
    return render_template("tutorial/index.html", title=_("How it works"))


@bp.route("/hide", methods=["POST"])
@login_required
def hide():
    """The × on the home page banner. (CSRFProtect checks the token.)"""
    mark_seen()
    return redirect(url_for("main.index"))
