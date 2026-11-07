from flask_babel import lazy_gettext as _l
from flask_wtf.file import FileAllowed, FileField
from wtforms import SubmitField, TextAreaField, URLField
from wtforms.validators import URL, Length, Optional

from app.forms import BaseForm
from app.wardrobe.forms import IMAGE_TYPES


class IdeaForm(BaseForm):
    """Save an idea: a pin link, or a picture from your phone. One is enough."""
    link = URLField(_l("Pinterest link"), validators=[
        Optional(), Length(max=500),
        URL(message=_l("Paste a full link, starting with http:// or https://.")),
    ])
    photo = FileField(_l("Or a picture"), validators=[
        FileAllowed(IMAGE_TYPES, _l("Images only (jpg, png, webp, gif).")),
    ])
    note = TextAreaField(_l("Note"), validators=[Optional(), Length(max=1000)])
    submit = SubmitField(_l("Save idea"))

    def validate(self, extra_validators=None):
        """The usual checks, plus: a link or a picture, not neither."""
        if not super().validate(extra_validators):
            return False
        if not self.link.data and not self.photo.data:
            self.link.errors.append(_l("Paste a pin link or choose a picture."))
            return False
        return True


class DeleteIdeaForm(BaseForm):
    """Only carries the CSRF token for the delete button."""
    submit = SubmitField(_l("Delete"))
