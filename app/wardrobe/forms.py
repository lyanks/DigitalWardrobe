from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, DateField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from app.wardrobe.choices import COLORS, SEASONS, STYLES

IMAGE_TYPES = ["jpg", "jpeg", "png", "webp", "gif"]


def _label(value):
    return value.capitalize()


class ItemForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=100)])
    # coerce=int: the browser sends "3" as text; we want the number 3.
    # The choices come from the database, so the route fills them in.
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    color = SelectField("Color", choices=[(c, _label(c)) for c in COLORS])
    season = SelectField("Season", choices=[(s, _label(s)) for s in SEASONS], default="all")
    style = SelectField("Style", choices=[("", "—")] + [(s, _label(s)) for s in STYLES])
    brand = StringField("Brand", validators=[Optional(), Length(max=60)])
    size = StringField("Size", validators=[Optional(), Length(max=20)])
    purchase_date = DateField("Bought on", validators=[Optional()])
    photo = FileField("Photo", validators=[
        FileAllowed(IMAGE_TYPES, "Images only (jpg, png, webp, gif)."),
    ])
    remove_photo = BooleanField("Remove the current photo")
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Save")


class DeleteForm(FlaskForm):
    """An empty form: it only carries the CSRF token for the delete button."""
    submit = SubmitField("Yes, delete it")
