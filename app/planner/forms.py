from flask_babel import lazy_gettext as _l, lazy_pgettext
from wtforms import SelectField, SelectMultipleField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from app.dates import DayMonthYearField
from app.forms import BaseForm


class ScheduleForm(BaseForm):
    # The route fills the choices with the user's own outfits.
    outfit_id = SelectField(_l("Outfit"), coerce=int, validators=[DataRequired()])
    # Turns "14.10.2026" into a Python date object (see app/dates.py).
    date = DayMonthYearField(_l("Day"), validators=[DataRequired()])
    note = StringField(_l("Note"), validators=[Optional(), Length(max=200)])
    submit = SubmitField(_l("Add to calendar"))


class LogLookForm(BaseForm):
    """Idea #1: what you wore on a day, picked from loose items."""
    # Filled with the user's own item ids by the route, like the outfit builder.
    item_ids = SelectMultipleField(_l("Items"), coerce=int)
    date = DayMonthYearField(_l("Day"), validators=[DataRequired()])
    # "Look" here is an outfit (образ); on the profile page it means the
    # app's appearance (вигляд), so the context word keeps them apart.
    submit = SubmitField(lazy_pgettext("outfit", "Save look"))

