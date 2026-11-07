"""Send an idea: users write what they'd like in the app, the admin reads it.

The ideas go to the Feedback table; the admin sees them on /admin/feedback.
Guests can read the page but not send: their visit is deleted when they
leave, so their idea would be lost with it.
"""
from datetime import timedelta

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app.extensions import db
from app.feedback.forms import FeedbackForm
from app.guests import is_guest
from app.models import Feedback, utcnow

bp = Blueprint("feedback", __name__, url_prefix="/feedback")

# Enough for a lot of ideas, too few to flood the admin page.
DAILY_LIMIT = 10


def sent_today(user_id):
    since = utcnow() - timedelta(days=1)
    return db.session.scalar(
        db.select(db.func.count()).select_from(Feedback)
        .where(Feedback.user_id == user_id, Feedback.created_at >= since)
    )


@bp.route("", methods=["GET", "POST"])
@login_required
def new():
    form = FeedbackForm()
    if not is_guest() and form.validate_on_submit():
        if sent_today(current_user.id) >= DAILY_LIMIT:
            flash(_("That's a lot of ideas for one day. Please send the rest tomorrow."), "error")
        else:
            db.session.add(Feedback(user_id=current_user.id, text=form.text.data))
            db.session.commit()
            flash(_("Thank you! Your idea was sent."), "success")
            return redirect(url_for("feedback.new"))
    return render_template("feedback/new.html", title=_("Send an idea"), form=form)
