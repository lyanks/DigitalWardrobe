from flask_babel import lazy_gettext as _l
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
PASSWORD_HINT = _l("At least 8 characters, with upper and lowercase letters, a number and a special character.")


# Shared by the register form and the profile form, so both follow the same rules.
USERNAME_RULES = [
    DataRequired(),
    Length(min=3, max=50),
    Regexp(r"^[A-Za-z0-9_.]+$", message=_l("Letters, numbers, dots and underscores only.")),
]


class RegistrationForm(BaseForm):
    username = StringField(_l("Username"), validators=USERNAME_RULES)
    email = StringField(_l("Email"), validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField(_l("Password"), validators=[DataRequired(), StrongPassword()],
                             description=PASSWORD_HINT)
    confirm = PasswordField(_l("Repeat password"), validators=[
        DataRequired(), EqualTo("password", message=_l("Passwords must match.")),
    ])
    submit = SubmitField(_l("Create account"))

    # WTForms calls any method named validate_<fieldname> automatically.
    def validate_username(self, field):
        if db.session.scalar(db.select(User).filter_by(username=field.data)):
            raise ValidationError(_l("That username is taken."))

    def validate_email(self, field):
        if db.session.scalar(db.select(User).filter_by(email=field.data.lower())):
            raise ValidationError(_l("An account with that email already exists."))


class LoginForm(BaseForm):
    login = StringField(_l("Username or email"), validators=[DataRequired()])
    password = PasswordField(_l("Password"), validators=[DataRequired()])
    submit = SubmitField(_l("Log in"))


class ProfileForm(BaseForm):
    username = StringField(_l("Username"), validators=USERNAME_RULES,
                           description=_l("You can log in with this or your email."))
    display_name = StringField(_l("Display name"), validators=[Optional(), Length(max=80)])
    avatar = FileField(_l("Avatar"), validators=[
        FileAllowed(IMAGE_TYPES, _l("Images only (jpg, png, webp, gif).")),
    ])
    submit = SubmitField(_l("Save profile"))

    def validate_username(self, field):
        # Taken by someone *else*? Keeping your own name is fine.
        other = db.session.scalar(db.select(User).filter_by(username=field.data))
        if other and other.id != current_user.id:
            raise ValidationError(_l("That username is taken."))


class ChangePasswordForm(BaseForm):
    # Optional here: an account made with Google has no password yet.
    # The route checks it for everyone else.
    current_password = PasswordField(_l("Current password"), validators=[Optional()])
    new_password = PasswordField(_l("New password"), validators=[DataRequired(), StrongPassword()],
                                 description=PASSWORD_HINT)
    confirm = PasswordField(_l("Repeat new password"), validators=[
        DataRequired(), EqualTo("new_password", message=_l("Passwords must match.")),
    ])
    submit = SubmitField(_l("Change password"))


class LookForm(BaseForm):
    """Idea #5: pick a theme and, if you like, your own accent colour."""
    theme = RadioField(_l("Theme"), choices=[(key, label) for key, (label, _) in THEMES.items()],
                       default=DEFAULT_THEME)
    # Rendered as <input type="color">, which always sends a colour like
    # "#c4a8ff". The checkbox says whether to use it or the theme's own.
    accent_color = StringField(_l("Accent colour"), default="#c4a8ff", validators=[
        Regexp(HEX_COLOR, message=_l("Pick a colour like #c4a8ff.")),
    ])
    use_theme_accent = BooleanField(_l("Use the theme's own colour"), default=True)
    submit = SubmitField(_l("Save look"))
