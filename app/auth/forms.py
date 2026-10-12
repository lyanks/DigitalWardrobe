from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import (
    DataRequired, Email, EqualTo, Length, Optional, Regexp, ValidationError,
)

from app.extensions import db
from app.models import User

IMAGE_TYPES = ["jpg", "jpeg", "png", "webp", "gif"]


class RegistrationForm(FlaskForm):
    username = StringField("Username", validators=[
        DataRequired(),
        Length(min=3, max=50),
        Regexp(r"^[A-Za-z0-9_.]+$", message="Letters, numbers, dots and underscores only."),
    ])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
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


class LoginForm(FlaskForm):
    login = StringField("Username or email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")


class ProfileForm(FlaskForm):
    display_name = StringField("Display name", validators=[Optional(), Length(max=80)])
    avatar = FileField("Avatar", validators=[
        FileAllowed(IMAGE_TYPES, "Images only (jpg, png, webp, gif)."),
    ])
    submit = SubmitField("Save profile")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[DataRequired()])
    new_password = PasswordField("New password", validators=[DataRequired(), Length(min=8)])
    confirm = PasswordField("Repeat new password", validators=[
        DataRequired(), EqualTo("new_password", message="Passwords must match."),
    ])
    submit = SubmitField("Change password")
