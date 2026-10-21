from flask_babel import lazy_gettext as _l
from flask_babel.speaklater import LazyString
from flask_wtf.file import FileAllowed, FileField
from wtforms import (BooleanField, DecimalField, HiddenField, SelectField, StringField,
                     SubmitField, TextAreaField, URLField)
from wtforms.validators import URL, DataRequired, Length, NumberRange, Optional

from app.dates import DayMonthYearField
from app.forms import BaseForm
from app.i18n import tr
from app import options
from app.wardrobe.choices import CURRENCIES, PRIORITIES

IMAGE_TYPES = ["jpg", "jpeg", "png", "webp", "gif"]


def _label(value):
    """"light blue" -> "Light blue" / "Світло-блакитний".

    Lazy: the form class is built once at start-up, but the label is
    translated each time it's shown, in that request's language.
    """
    return LazyString(lambda: tr(value).capitalize())


class ItemForm(BaseForm):
    name = StringField(_l("Name"), validators=[DataRequired(), Length(max=100)])
    # coerce=int: the browser sends "3" as text; we want the number 3.
    # These four lists come from the database (the admin can change them),
    # so __init__ below fills them in for each request.
    category_id = SelectField(_l("Category"), coerce=int, validators=[DataRequired()])
    color = SelectField(_l("Color"))
    season = SelectField(_l("Season"), default="all")
    style = SelectField(_l("Style"))
    brand = StringField(_l("Brand"), validators=[Optional(), Length(max=60)])
    size = StringField(_l("Size"), validators=[Optional(), Length(max=20)])
    purchase_date = DayMonthYearField(_l("Bought on"), validators=[Optional()])
    photo = FileField(_l("Photo"), validators=[
        FileAllowed(IMAGE_TYPES, _l("Images only (jpg, png, webp, gif).")),
    ])
    # Ticked by default: product photos on white look better cut out.
    # Untick it for white clothes on a white background.
    remove_white = BooleanField(_l("Remove the white background"), default=True)
    remove_photo = BooleanField(_l("Remove the current photo"))
    notes = TextAreaField(_l("Notes"), validators=[Optional(), Length(max=2000)])

    # Only on wishlist items. The routes delete these fields from the form
    # for clothes you own, so they don't show up or get validated there.
    shop_url = URLField(_l("Link to the shop"), validators=[
        Optional(), URL(message=_l("Paste a full link, starting with http:// or https://.")),
        Length(max=500),
    ])
    # places=2: the value comes back as Decimal("49.90"), ready for Numeric.
    price = DecimalField(_l("Price"), places=2, validators=[
        Optional(), NumberRange(min=0, message=_l("A price can't be negative.")),
    ])
    currency = SelectField(_l("Currency"), choices=CURRENCIES)
    # coerce=int turns "1" into 1; "" (not set) is allowed by Optional().
    priority = SelectField(
        _l("Priority"), coerce=int, default=0,
        # The labels are data words (app/i18n.py), translated when shown.
        choices=[(0, "—")] + [(n, LazyString(tr, label)) for n, label in PRIORITIES.items()],
    )
    # Filled in by autofill.js with the shop's photo link. If there's no
    # uploaded photo, the server downloads this one when you save.
    image_url = HiddenField()
    submit = SubmitField(_l("Save"))


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        item = kwargs.get("obj")

        def keep_current(values, current):
            # An item keeps a value the admin has hidden since.
            if current and current not in values:
                values.append(current)
            return values

        categories = options.categories()
        if item and item.category and item.category.hidden:
            categories.append(item.category)
        self.category_id.choices = [(c.id, tr(c.name)) for c in categories]
        self.color.choices = [(c, _label(c)) for c in
                              keep_current(options.values("color"), getattr(item, "color", None))]
        self.season.choices = [(s, _label(s)) for s in
                               keep_current(options.values("season"), getattr(item, "season", None))]
        self.style.choices = [("", "—")] + [(s, _label(s)) for s in
                                            keep_current(options.values("style"), getattr(item, "style", None))]


WISH_FIELDS = ("shop_url", "price", "currency", "priority", "image_url")


class BoughtForm(BaseForm):
    """Only the CSRF token, for the "I bought it" button."""
    submit = SubmitField(_l("I bought it"))


class DeleteForm(BaseForm):
    """An empty form: it only carries the CSRF token for the delete button."""
    submit = SubmitField(_l("Yes, delete it"))
