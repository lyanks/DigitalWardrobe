from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth.forms import ChangePasswordForm, LoginForm, ProfileForm, RegistrationForm
from app.extensions import db
from app.models import User
from app.services.images import InvalidImageError, delete_image, save_image

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
        db.session.commit()

        login_user(user)
        flash("Welcome! Your account is ready.", "success")
        # Post/Redirect/Get: after a successful POST, always redirect,
        # so refreshing the page doesn't submit the form twice.
        return redirect(url_for("main.index"))

    # Either a GET, or a POST with errors: show the form (errors included).
    return render_template("auth/register.html", title="Register", form=form)


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
            flash("Wrong username or password.", "error")
            return render_template("auth/login.html", title="Log in", form=form), 401

        login_user(user)
        flash(f"Hi, {user.shown_name}!", "success")
        return redirect(_safe_next_url() or url_for("main.index"))

    return render_template("auth/login.html", title="Log in", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    # Two forms on one page. The `prefix` keeps their field names apart,
    # and each submit button tells us which one was sent.
    profile_form = ProfileForm(prefix="profile")
    password_form = ChangePasswordForm(prefix="pw")

    if profile_form.submit.data and profile_form.validate_on_submit():
        try:
            # Check the photo first: if it's broken, nothing is changed.
            new_avatar = None
            if profile_form.avatar.data:
                new_avatar = save_image(profile_form.avatar.data, "avatars", max_size=400)
        except InvalidImageError as error:
            profile_form.avatar.errors.append(str(error))
        else:
            current_user.display_name = profile_form.display_name.data or None
            if new_avatar:
                delete_image(current_user.avatar_path)
                current_user.avatar_path = new_avatar
            db.session.commit()
            flash("Profile saved.", "success")
            return redirect(url_for("auth.profile"))

    if password_form.submit.data and password_form.validate_on_submit():
        if not current_user.check_password(password_form.current_password.data):
            password_form.current_password.errors.append("That is not your current password.")
        else:
            current_user.set_password(password_form.new_password.data)
            db.session.commit()
            flash("Password changed.", "success")
            return redirect(url_for("auth.profile"))

    if request.method == "GET":
        # Pre-fill the form with what is already saved.
        profile_form.display_name.data = current_user.display_name

    return render_template(
        "auth/profile.html", title="Profile",
        profile_form=profile_form, password_form=password_form,
    )


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
