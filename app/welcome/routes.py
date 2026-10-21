"""Idea #7: "Set up your wardrobe", a short wizard right after sign-up.

Three steps: 1 name, 2 why you use the app, 3 theme. Each step has "Skip",
and "Skip the setup" ends it at once. Finishing (or skipping) fills in
User.onboarded_at, so the wizard never shows up again. Everything can be
changed later on the profile page.
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_required

from app.extensions import db
from app.models import UserGoal, utcnow
from app.themes import THEMES
from app.welcome.forms import GoalsForm, NameForm, SkipForm, WelcomeLookForm

bp = Blueprint("welcome", __name__, url_prefix="/welcome")

# step number -> (heading, form class)
STEPS = {
    1: (_l("What should we call you?"), NameForm),
    2: (_l("Why do you use Digital Wardrobe?"), GoalsForm),
    3: (_l("Pick your look"), WelcomeLookForm),
}


@bp.before_request
@login_required
def require_login():
    """Only for logged-in people."""


def needs_setup(user):
    """True if this user hasn't finished or skipped the wizard yet."""
    return user.onboarded_at is None


@bp.route("")
def start():
    return redirect(url_for("welcome.step", number=1))


@bp.route("/<int:number>", methods=["GET", "POST"])
def step(number):
    if number not in STEPS:
        abort(404)
    heading, form_class = STEPS[number]
    form = form_class()

    # "Skip" is a second submit button with name="skip": go on, save nothing.
    if request.method == "POST" and "skip" in request.form:
        return _next(number)

    if form.validate_on_submit():
        SAVERS[number](form)
        db.session.commit()
        return _next(number)

    if request.method == "GET":
        _prefill(number, form)
    return render_template("welcome/step.html", title=_("Set up"), heading=heading, form=form,
                           number=number, total=len(STEPS), themes=THEMES, skip_form=SkipForm())


@bp.route("/skip", methods=["POST"])
def skip_all():
    if SkipForm().validate_on_submit():
        return _finish()
    return redirect(url_for("welcome.step", number=1))


def _next(number):
    if number < len(STEPS):
        return redirect(url_for("welcome.step", number=number + 1))
    return _finish()


def _finish():
    current_user.onboarded_at = utcnow()
    db.session.commit()
    flash(_("All set! You can change any of this on your profile page."), "success")
    return redirect(url_for("main.index"))


# ---------- what each step saves and shows ----------

def _save_name(form):
    current_user.username = form.username.data
    current_user.display_name = form.display_name.data or None


def save_goals(user, keys):
    """Replace the user's goals with these keys. Also used by the profile page."""
    user.goals = [UserGoal(goal=key) for key in keys]


def _save_look(form):
    current_user.theme = form.theme.data
    current_user.accent_color = (
        None if form.use_theme_accent.data else form.accent_color.data.lower()
    )


SAVERS = {
    1: _save_name,
    2: lambda form: save_goals(current_user, form.goals.data),
    3: _save_look,
}


def _prefill(number, form):
    if number == 1:
        form.username.data = current_user.username
        form.display_name.data = current_user.display_name
    elif number == 2:
        form.goals.data = current_user.goal_keys
    else:
        form.theme.data = current_user.theme
        form.use_theme_accent.data = current_user.accent_color is None
        form.accent_color.data = current_user.accent_color or "#c4a8ff"
