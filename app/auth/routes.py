import re
from urllib.parse import urlsplit

from authlib.integrations.base_client import OAuthError
from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for,
)
from flask_babel import gettext as _
from flask_login import current_user, login_required, login_user, logout_user

from app.auth.forms import (
    INVALID_INVITE, ChangePasswordForm, LoginForm, LookForm, ProfileForm, RegistrationForm,
)
from app.extensions import db, oauth
from app.invites import find_usable, tidy, use_invite
from app.models import User
from app.services.images import InvalidImageError, delete_image, save_image
from app.themes import THEMES
from app.welcome.routes import needs_setup

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegistrationForm()
    # GET: validate_on_submit() is False, so we just show the empty form.
    # POST: it checks every validator; True only if all pass.
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data.lower())
        user.set_password(form.password.data)
        db.session.add(user)
        # The account and the used-up code are saved together, or not at all.
        invite = find_usable(form.invite_code.data)
        if invite is None or not use_invite(invite, user):
            db.session.rollback()
            form.invite_code.errors.append(INVALID_INVITE)
            return render_template("auth/register.html", title=_("Sign up"), form=form)
        db.session.commit()

        login_user(user)
        flash(_("Welcome! Your account is ready."), "success")
        # Post/Redirect/Get: after a successful POST, always redirect,
        # so refreshing the page doesn't submit the form twice.
        # A new account goes through the setup wizard first (idea #7).
        return redirect(url_for("welcome.start"))

    # Either a GET, or a POST with errors: show the form (errors included).
    return render_template("auth/register.html", title=_("Sign up"), form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        value = form.login.data.strip()
        user = db.session.scalar(
            db.select(User).where((User.username == value) | (User.email == value.lower()))
        )
        # Same message whether the user doesn't exist or the password is
        # wrong, so nobody can probe which usernames exist.
        if user is None or not user.check_password(form.password.data):
            flash(_("Wrong username or password."), "error")
            return render_template("auth/login.html", title=_("Log in"), form=form), 401

        login_user(user)
        flash(_("Hi, %(name)s!", name=user.shown_name), "success")
        return redirect(_after_login(user))

    return render_template("auth/login.html", title=_("Log in"), form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash(_("You have been logged out."), "info")
    return redirect(url_for("main.index"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    # Two forms on one page. The `prefix` keeps their field names apart,
    # and each submit button tells us which one was sent.
    profile_form = ProfileForm(prefix="profile")
    password_form = ChangePasswordForm(prefix="pw")
    look_form = LookForm(prefix="look")

    if look_form.submit.data and look_form.validate_on_submit():
        current_user.theme = look_form.theme.data
        current_user.accent_color = (
            None if look_form.use_theme_accent.data else look_form.accent_color.data.lower()
        )
        db.session.commit()
        flash(_("Your new look is saved."), "success")
        return redirect(url_for("auth.profile"))

    if profile_form.submit.data and profile_form.validate_on_submit():
        try:
            # Check the photo first: if it's broken, nothing is changed.
            new_avatar = None
            if profile_form.avatar.data:
                new_avatar = save_image(profile_form.avatar.data, "avatars", max_size=400)
        except InvalidImageError as error:
            profile_form.avatar.errors.append(str(error))
        else:
            current_user.username = profile_form.username.data
            current_user.display_name = profile_form.display_name.data or None
            if new_avatar:
                delete_image(current_user.avatar_path)
                current_user.avatar_path = new_avatar
            db.session.commit()
            flash(_("Profile saved."), "success")
            return redirect(url_for("auth.profile"))

    if password_form.submit.data and password_form.validate_on_submit():
        if current_user.has_password and not current_user.check_password(
            password_form.current_password.data or ""
        ):
            password_form.current_password.errors.append(_("That is not your current password."))
        else:
            current_user.set_password(password_form.new_password.data)
            db.session.commit()
            flash(_("Password changed."), "success")
            return redirect(url_for("auth.profile"))

    if request.method == "GET":
        # Pre-fill the form with what is already saved.
        profile_form.username.data = current_user.username
        profile_form.display_name.data = current_user.display_name
        look_form.theme.data = current_user.theme
        look_form.use_theme_accent.data = current_user.accent_color is None
        look_form.accent_color.data = current_user.accent_color or "#c4a8ff"

    return render_template(
        "auth/profile.html", title=_("Profile"),
        profile_form=profile_form, password_form=password_form, look_form=look_form,
        themes=THEMES,
    )


# ---------- Sign in with Google ----------

@bp.route("/login/google", methods=["GET", "POST"])
def google_login():
    if not current_app.config["GOOGLE_CLIENT_ID"]:
        abort(404)  # not set up on this computer
    # The Google button on the sign-up page sends the invite code along
    # (POST). It waits in the session until Google sends the person back.
    if request.method == "POST":
        code = request.form.get("invite_code", "")
        if not find_usable(code):
            flash(INVALID_INVITE, "error")
            return redirect(url_for("auth.register"))
        session["invite_code"] = tidy(code)
    # Step 1: send the browser to Google's sign-in page. Google will send
    # it back to the callback URL below with a one-time code.
    callback = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(callback)


@bp.route("/login/google/callback")
def google_callback():
    if not current_app.config["GOOGLE_CLIENT_ID"]:
        abort(404)
    try:
        # Step 2: our server swaps the one-time code for a token, directly
        # with Google. The token contains who the person is ("userinfo").
        token = oauth.google.authorize_access_token()
    except OAuthError:
        flash(_("Google sign-in was cancelled or failed. Please try again."), "error")
        return redirect(url_for("auth.login"))

    info = token.get("userinfo") or {}
    if not info.get("email_verified"):
        flash(_("Your Google account's email isn't verified, so we can't use it."), "error")
        return redirect(url_for("auth.login"))

    user = _find_or_create_google_user(info)
    if user is None:
        flash(_("To make a new account, enter your invite code on the sign-up page first."), "error")
        return redirect(url_for("auth.register"))
    login_user(user)
    flash(_("Hi, %(name)s!", name=user.shown_name), "success")
    return redirect(_after_login(user))


def _after_login(user):
    """Where to go after logging in: the setup wizard if it isn't done yet,
    otherwise the page you came for (?next=...) or the home page."""
    if needs_setup(user):
        return url_for("welcome.start")
    return _safe_next_url() or url_for("main.index")


def _find_or_create_google_user(info):
    """Step 3: match the Google account to one of our users.

    None means it's a new person without a usable invite code.
    """
    google_id = info["sub"]  # Google's permanent id for this person
    email = info["email"].lower()

    # Signed in with Google before?
    user = db.session.scalar(db.select(User).filter_by(google_id=google_id))
    if user:
        return user

    # Already registered with the same (Google-verified) email? Link them.
    user = db.session.scalar(db.select(User).filter_by(email=email))
    if user:
        user.google_id = google_id
        db.session.commit()
        return user

    # Brand new: only with an invite code (sent from the sign-up page).
    invite = find_usable(session.pop("invite_code", ""))
    if invite is None:
        return None
    # Create an account without a password.
    user = User(
        username=_free_username(email.split("@")[0]),
        email=email,
        google_id=google_id,
        display_name=(info.get("name") or "")[:80] or None,
    )
    db.session.add(user)
    if not use_invite(invite, user):
        db.session.rollback()
        return None
    db.session.commit()
    return user


def _free_username(wanted):
    """Turn an email name into a valid username nobody has yet: anna.k -> anna.k2."""
    base = re.sub(r"[^A-Za-z0-9_.]", "", wanted)[:45] or "user"
    base = base.ljust(3, "_")  # usernames need at least 3 characters
    candidate, number = base, 1
    while db.session.scalar(db.select(User).filter_by(username=candidate)):
        number += 1
        candidate = f"{base}{number}"
    return candidate


def _safe_next_url():
    """Return ?next=... only if it points inside this site.

    @login_required sends you to /login?next=/profile. Without this check,
    a link like /login?next=https://evil.example would send you to another
    site right after logging in (an "open redirect").
    """
    target = request.args.get("next")
    if target and target.startswith("/") and "\\" not in target and urlsplit(target).netloc == "":
        return target
    return None
