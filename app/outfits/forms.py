from flask_babel import lazy_gettext as _l
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, SelectField, SelectMultipleField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from app.forms import BaseForm
from app.i18n import tr
from app import options
from app.wardrobe.forms import IMAGE_TYPES


class OutfitForm(BaseForm):
    name = StringField(_l("Name"), validators=[DataRequired(), Length(max=100)])
    # The occasion names are filled in __init__ below, in the page's language.
    occasion = SelectField(_l("Occasion"))
    # Several values under one name: the browser sends item_ids=3&item_ids=7...
    # The route fills `choices` with the user's own item ids, and WTForms
    # rejects any id that isn't in that list. So you can't sneak someone
    # else's item into your outfit by editing the page.
    # The template draws these as photo checkboxes grouped by category.
    item_ids = SelectMultipleField(_l("Items"), coerce=int)
    photo = FileField(_l("Photo of the outfit"), description=_l("Optional: a picture of you wearing it."),
                      validators=[FileAllowed(IMAGE_TYPES, _l("Images only (jpg, png, webp, gif)."))])
    remove_photo = BooleanField(_l("Remove the current photo"))
    notes = TextAreaField(_l("Notes"), validators=[Optional(), Length(max=2000)])
    submit = SubmitField(_l("Save outfit"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Built for each request, so "work" shows as "Робота" in Ukrainian.
        # The list comes from the database (the admin can change it). An
        # outfit keeps an occasion the admin has hidden since.
        occasions = options.values("occasion")
        current = getattr(kwargs.get("obj"), "occasion", None)
        if current and current not in occasions:
            occasions.append(current)
        self.occasion.choices = [("", "—")] + [(o, tr(o).capitalize()) for o in occasions]


class DeleteOutfitForm(BaseForm):
    """Only carries the CSRF token for the delete button."""
    submit = SubmitField(_l("Yes, delete it"))
