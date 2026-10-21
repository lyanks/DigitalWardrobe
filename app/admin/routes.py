"""The admin pages, for your account only (ADMIN_EMAIL in .env).

Every route in this blueprint goes through lock() first. Anyone else gets
"Page not found", so strangers don't even learn that /admin exists.
"""
from datetime import date

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_babel import force_locale
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l
from flask_babel import ngettext
from flask_login import current_user

from app import options
from app.admin.access import is_admin
from app.admin.forms import InviteForm, OptionForm
from app.extensions import db
from app.goals import GOALS
from app.i18n import tr
from app.invites import create_invite
from app.models import OWNED, Category, GoalAnswer, InviteCode, Item, Option, Outfit, User, utcnow
from app.services.stats import breakdown

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
def lock():
    """Runs before every admin page. A new page can't forget it."""
    if not is_admin(current_user):
        abort(404)


# ---------- Dashboard ----------

@bp.route("")
def index():
    def count(query):
        return db.session.scalar(db.select(db.func.count()).select_from(query.subquery()))

    today = date.today()
    statuses = [invite.status(today) for invite in db.session.scalars(db.select(InviteCode))]
    numbers = {
        "users": count(db.select(User.id)),
        "clothes": count(db.select(Item.id).where(Item.status == OWNED)),
        "outfits": count(db.select(Outfit.id)),
        "waiting": statuses.count("waiting"),
        "used": statuses.count("used"),
    }
    answers = db.session.execute(
        db.select(GoalAnswer.goal, db.func.count()).group_by(GoalAnswer.goal)
    ).all()
    # Every reason gets a row, also the ones nobody picked yet.
    found = dict(answers)
    goals = breakdown([(key, found.get(key, 0)) for key in GOALS])
    biggest = max((row["count"] for row in goals), default=0)
    for row in goals:
        row["label"] = tr(GOALS[row["label"]])
        if not biggest:
            row["percent"] = 0
    return render_template("admin/dashboard.html", title=_("Admin"), numbers=numbers,
                           goals=goals, answered=sum(found.values()))


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


# ---------- Shared options ----------

KIND_LABELS = {
    "category": _l("Categories"),
    "color": _l("Colors"),
    "season": _l("Seasons"),
    "style": _l("Styles"),
    "occasion": _l("Occasions"),
}
# "All seasons" is how the season filter works, so it can't change.
PROTECTED = {("season", "all")}


def _check(kind):
    if kind not in KIND_LABELS:
        abort(404)


def _model(kind):
    return Category if kind == "category" else Option


def _name(row):
    return row.name if isinstance(row, Category) else row.value


def _rows(kind, include_hidden=True):
    return (options.categories(include_hidden) if kind == "category"
            else options.options(kind, include_hidden))


def _get(kind, row_id):
    row = db.session.get(_model(kind), row_id)
    if row is None or (kind != "category" and row.kind != kind):
        abort(404)
    return row


def _uses(kind, row):
    if kind == "category":
        return db.session.scalar(db.select(db.func.count()).where(Item.category_id == row.id))
    return options.uses(kind, row.value)


def _form(kind, **kwargs):
    form = OptionForm(**kwargs)
    if kind != "color":
        del form.hex
    if kind != "category":
        del form.slot
    return form


def _clean_name(kind, text):
    # Option values are lowercase ("light blue"); pages capitalise them.
    # Categories are names ("Tops") and keep their capitals.
    text = " ".join(text.split())
    return text if kind == "category" else text.lower()


def _taken(kind, name, except_row=None):
    return any(_name(row).lower() == name.lower() and row is not except_row
               for row in _rows(kind))


def _ukrainian(text):
    """The Ukrainian name messages.po has for this English word, or ""."""
    with force_locale("uk"):
        translated = tr(text)
    return "" if translated == text else translated


@bp.route("/options")
def options_index():
    return redirect(url_for("admin.option_list", kind="category"))


@bp.route("/options/<kind>", methods=["GET", "POST"])
def option_list(kind):
    _check(kind)
    form = _form(kind)
    if form.validate_on_submit():
        name = _clean_name(kind, form.name.data)
        if _taken(kind, name):
            form.name.errors.append(_("That one is already in the list."))
        else:
            rows = _rows(kind)
            fields = {"name_uk": form.name_uk.data or None,
                      "position": max((row.position for row in rows), default=0) + 1}
            if kind == "category":
                row = Category(name=name, slot=form.slot.data, **fields)
            else:
                row = Option(kind=kind, value=name, hex=form.hex.data if form.hex else None, **fields)
            db.session.add(row)
            db.session.commit()
            options.forget()
            flash(_("Added “%(name)s”.", name=name), "success")
            return redirect(url_for("admin.option_list", kind=kind))

    rows = [{"row": row, "name": _name(row), "uk": row.name_uk or _ukrainian(_name(row)),
             "uses": _uses(kind, row), "protected": (kind, _name(row)) in PROTECTED}
            for row in _rows(kind)]
    return render_template("admin/options.html", title=KIND_LABELS[kind], kind=kind,
                           kinds=KIND_LABELS, rows=rows, form=form)


@bp.route("/options/<kind>/<int:row_id>/edit", methods=["GET", "POST"])
def option_edit(kind, row_id):
    _check(kind)
    row = _get(kind, row_id)
    old_name = _name(row)
    if (kind, old_name) in PROTECTED:
        abort(404)
    form = _form(kind)
    form.submit.label.text = _("Save")
    uses = _uses(kind, row)
    if uses:
        form.name.description = _("Renaming changes it on everything that uses it.")

    if form.validate_on_submit():
        name = _clean_name(kind, form.name.data)
        if _taken(kind, name, except_row=row):
            form.name.errors.append(_("That one is already in the list."))
        else:
            row.name_uk = form.name_uk.data or None
            if kind == "category":
                row.name = name
                row.slot = form.slot.data
            else:
                if form.hex:
                    row.hex = form.hex.data
                if name != old_name:
                    options.rename(kind, old_name, name)  # every item that had it
                    row.value = name
            db.session.commit()
            options.forget()
            flash(_("Saved."), "success")
            return redirect(url_for("admin.option_list", kind=kind))
    elif request.method == "GET":
        form.name.data = old_name
        # Pre-fill the Ukrainian name from messages.po, so renaming the
        # English word later doesn't lose the translation.
        form.name_uk.data = row.name_uk or _ukrainian(old_name)
        if form.hex:
            form.hex.data = row.hex
        if form.slot:
            form.slot.data = row.slot

    return render_template("admin/option_edit.html", title=_("Edit “%(name)s”", name=old_name),
                           kind=kind, kinds=KIND_LABELS, row=row, form=form, uses=uses)


@bp.route("/options/<kind>/<int:row_id>/remove", methods=["POST"])
def option_remove(kind, row_id):
    _check(kind)
    row = _get(kind, row_id)
    name = _name(row)
    if (kind, name) in PROTECTED:
        abort(404)
    if not row.hidden and len(_rows(kind, include_hidden=False)) == 1:
        flash(_("Keep at least one, or the item form has nothing to offer."), "error")
        return redirect(url_for("admin.option_list", kind=kind))

    uses = _uses(kind, row)
    if uses:
        # Clothes already use it: hide it instead, so they keep their value.
        row.hidden = True
        flash(ngettext("“%(name)s” is used by %(num)d item, so it's hidden instead: "
                       "new items can't pick it.",
                       "“%(name)s” is used by %(num)d items, so it's hidden instead: "
                       "new items can't pick it.", uses, name=name), "info")
    else:
        db.session.delete(row)
        flash(_("Removed “%(name)s”.", name=name), "info")
    db.session.commit()
    options.forget()
    return redirect(url_for("admin.option_list", kind=kind))


@bp.route("/options/<kind>/<int:row_id>/show", methods=["POST"])
def option_show(kind, row_id):
    _check(kind)
    row = _get(kind, row_id)
    row.hidden = False
    db.session.commit()
    options.forget()
    flash(_("“%(name)s” can be picked again.", name=_name(row)), "success")
    return redirect(url_for("admin.option_list", kind=kind))


@bp.route("/options/<kind>/order", methods=["POST"])
def option_order(kind):
    """Drag and drop on the list sends {"ids": [3, 1, 2]} (admin_order.js)."""
    _check(kind)
    rows = {row.id: row for row in _rows(kind)}
    ids = (request.get_json(silent=True) or {}).get("ids", [])
    if sorted(ids) != sorted(rows):
        return jsonify(error="The list changed. Reload the page."), 400
    for position, row_id in enumerate(ids):
        rows[row_id].position = position
    db.session.commit()
    options.forget()
    return jsonify(ok=True)
