from flask_login import current_user
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, PasswordField, RadioField, StringField, SubmitField
from wtforms.validators import (
    DataRequired, Email, EqualTo, Length, Optional, Regexp, ValidationError,
)

from app.auth.validators import StrongPassword
from app.extensions import db
from app.forms import BaseForm
from app.models import User
from app.themes import DEFAULT_THEME, HEX_COLOR, THEMES

IMAGE_TYPES = ["jpg", "jpeg", "png", "webp", "gif"]
PASSWORD_HINT = "At least 8 characters, with upper and lowercase letters, a number and a special character."


# Shared by the register form and the profile form, so both follow the same rules.
USERNAME_RULES = [
    DataRequired(),
    Length(min=3, max=50),
    Regexp(r"^[A-Za-z0-9_.]+$", message="Letters, numbers, dots and underscores only."),
]


class RegistrationForm(BaseForm):
    username = StringField("Username", validators=USERNAME_RULES)
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), StrongPassword()],
                             description=PASSWORD_HINT)
    confirm = PasswordField("Repeat password", validators=[
        DataRequired(), EqualTo("password", message="Passwords must match."),
    ])
    submit = SubmitField("Create account")

    # WTForms calls any method named validate_<fieldname> automatically.
    def validate_username(self, field):
        if db.session.scalar(db.select(User).filter_by(username=field.data)):
            raise ValidationError("That username is taken.")

    def validate_email(self, field):
        if db.session.scalar(db.select(User).filter_by(email=field.data.lower())):
            raise ValidationError("An account with that email already exists.")


class LoginForm(BaseForm):
    login = StringField("Username or email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")


class ProfileForm(BaseForm):
    username = StringField("Username", validators=USERNAME_RULES,
                           description="You can log in with this or your email.")
    display_name = StringField("Display name", validators=[Optional(), Length(max=80)])
    avatar = FileField("Avatar", validators=[
        FileAllowed(IMAGE_TYPES, "Images only (jpg, png, webp, gif)."),
    ])
    submit = SubmitField("Save profile")

    def validate_username(self, field):
        # Taken by someone *else*? Keeping your own name is fine.
        other = db.session.scalar(db.select(User).filter_by(username=field.data))
        if other and other.id != current_user.id:
            raise ValidationError("That username is taken.")


class ChangePasswordForm(BaseForm):
    # Optional here: an account made with Google has no password yet.
    # The route checks it for everyone else.
    current_password = PasswordField("Current password", validators=[Optional()])
    new_password = PasswordField("New password", validators=[DataRequired(), StrongPassword()],
                                 description=PASSWORD_HINT)
    confirm = PasswordField("Repeat new password", validators=[
        DataRequired(), EqualTo("new_password", message="Passwords must match."),
    ])
    submit = SubmitField("Change password")


class LookForm(BaseForm):
    """Idea #5: pick a theme and, if you like, your own accent colour."""
    theme = RadioField("Theme", choices=[(key, label) for key, (label, _) in THEMES.items()],
                       default=DEFAULT_THEME)
    # Rendered as <input type="color">, which always sends a colour like
    # "#c4a8ff". The checkbox says whether to use it or the theme's own.
    accent_color = StringField("Accent colour", default="#c4a8ff", validators=[
        Regexp(HEX_COLOR, message="Pick a colour like #c4a8ff."),
    ])
    use_theme_accent = BooleanField("Use the theme's own colour", default=True)
    submit = SubmitField("Save look")
