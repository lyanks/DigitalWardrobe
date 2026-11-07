from flask_babel import lazy_gettext as _l
from wtforms import SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length

from app.forms import BaseForm


class FeedbackForm(BaseForm):
    text = TextAreaField(_l("Your idea"), validators=[DataRequired(), Length(max=2000)],
                         description=_l("What would make the app better for you? Up to 2000 characters."))
    submit = SubmitField(_l("Send"))
