from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, SelectField, SelectMultipleField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from app.forms import BaseForm
from app.wardrobe.choices import OCCASIONS
from app.wardrobe.forms import IMAGE_TYPES


class OutfitForm(BaseForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=100)])
    occasion = SelectField("Occasion", choices=[("", "—")] + [(o, o.capitalize()) for o in OCCASIONS])
    # Several values under one name: the browser sends item_ids=3&item_ids=7...
    # The route fills `choices` with the user's own item ids, and WTForms
    # rejects any id that isn't in that list. So you can't sneak someone
    # else's item into your outfit by editing the page.
    # The template draws these as photo checkboxes grouped by category.
    item_ids = SelectMultipleField("Items", coerce=int)
    photo = FileField("Photo of the outfit", description="Optional: a picture of you wearing it.",
                      validators=[FileAllowed(IMAGE_TYPES, "Images only (jpg, png, webp, gif).")])
    remove_photo = BooleanField("Remove the current photo")
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Save outfit")


class DeleteOutfitForm(BaseForm):
    """Only carries the CSRF token for the delete button."""
    submit = SubmitField("Yes, delete it")
