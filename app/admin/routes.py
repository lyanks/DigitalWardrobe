"""The admin pages, for your account only (ADMIN_EMAIL in .env).

Every route in this blueprint goes through lock() first. Anyone else gets
"Page not found", so strangers don't even learn that /admin exists.
"""
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_babel import gettext as _
from flask_login import current_user

from app.admin.access import is_admin
from app.admin.forms import InviteForm
from app.extensions import db
from app.invites import create_invite
from app.models import InviteCode, utcnow

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
def lock():
    """Runs before every admin page. A new page can't forget it."""
    if not is_admin(current_user):
        abort(404)


@bp.route("")
def index():
    return redirect(url_for("admin.invites"))


@bp.route("/invites", methods=["GET", "POST"])
def invites():
    form = InviteForm()
    if form.validate_on_submit():
        invite = create_invite(form.note.data, form.expires_on.data)
        flash(_("New code: %(code)s", code=invite.code), "success")
        return redirect(url_for("admin.invites"))

    codes = db.session.scalars(
        db.select(InviteCode).order_by(InviteCode.created_at.desc(), InviteCode.id.desc())
    ).all()
    return render_template("admin/invites.html", title=_("Invite codes"), form=form,
                           codes=codes, today=date.today())


@bp.route("/invites/<int:invite_id>/off", methods=["POST"])
def turn_off(invite_id):
    invite = db.get_or_404(InviteCode, invite_id)
    # A used code stays as it is: it already did its job.
    if invite.used_at is None and invite.disabled_at is None:
        invite.disabled_at = utcnow()
        db.session.commit()
        flash(_("%(code)s is turned off.", code=invite.code), "info")
    return redirect(url_for("admin.invites"))
