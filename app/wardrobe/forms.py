from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (BooleanField, DecimalField, HiddenField, SelectField, StringField,
                     SubmitField, TextAreaField, URLField)
from wtforms.validators import URL, DataRequired, Length, NumberRange, Optional

from app.dates import DayMonthYearField
from app.wardrobe.choices import COLORS, CURRENCIES, PRIORITIES, SEASONS, STYLES

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
    purchase_date = DayMonthYearField("Bought on", validators=[Optional()])
    photo = FileField("Photo", validators=[
        FileAllowed(IMAGE_TYPES, "Images only (jpg, png, webp, gif)."),
    ])
    # Ticked by default: product photos on white look better cut out.
    # Untick it for white clothes on a white background.
    remove_white = BooleanField("Remove the white background", default=True)
    remove_photo = BooleanField("Remove the current photo")
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])

    # Only on wishlist items. The routes delete these fields from the form
    # for clothes you own, so they don't show up or get validated there.
    shop_url = URLField("Link to the shop", validators=[
        Optional(), URL(message="Paste a full link, starting with http:// or https://."),
        Length(max=500),
    ])
    # places=2: the value comes back as Decimal("49.90"), ready for Numeric.
    price = DecimalField("Price", places=2, validators=[
        Optional(), NumberRange(min=0, message="A price can't be negative."),
    ])
    currency = SelectField("Currency", choices=CURRENCIES)
    # coerce=int turns "1" into 1; "" (not set) is allowed by Optional().
    priority = SelectField(
        "Priority", choices=[(0, "—")] + list(PRIORITIES.items()), coerce=int, default=0,
    )
    # Filled in by autofill.js with the shop's photo link. If there's no
    # uploaded photo, the server downloads this one when you save.
    image_url = HiddenField()
    submit = SubmitField("Save")


WISH_FIELDS = ("shop_url", "price", "currency", "priority", "image_url")


class BoughtForm(FlaskForm):
    """Only the CSRF token, for the "I bought it" button."""
    submit = SubmitField("I bought it")


class DeleteForm(FlaskForm):
    """An empty form: it only carries the CSRF token for the delete button."""
    submit = SubmitField("Yes, delete it")
