from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError

from app.dates import DayMonthYearField
from app.forms import BaseForm

# Longer trips are more likely a typo in the year.
MAX_TRIP_DAYS = 60


class TripForm(BaseForm):
    name = StringField(_l("Where to?"), validators=[DataRequired(), Length(max=80)],
                       render_kw={"placeholder": _l("Lviv weekend")})
    start_date = DayMonthYearField(_l("From"), validators=[DataRequired()])
    end_date = DayMonthYearField(_l("To"), validators=[DataRequired()])
    submit = SubmitField(_l("Pack a suitcase"))

    # WTForms calls validate_<field name> by itself, after the field's own
    # validators. It's the place for rules that need two fields at once.
    def validate_end_date(self, field):
        start = self.start_date.data
        if start and field.data:
            if field.data < start:
                raise ValidationError(_("The trip can't end before it starts."))
            if (field.data - start).days + 1 > MAX_TRIP_DAYS:
                raise ValidationError(_("That's more than %(num)s days. Check the year?", num=MAX_TRIP_DAYS))
