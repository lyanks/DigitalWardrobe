from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError

from app.dates import DayMonthYearField

# Longer trips are more likely a typo in the year.
MAX_TRIP_DAYS = 60


class TripForm(FlaskForm):
    name = StringField("Where to?", validators=[DataRequired(), Length(max=80)],
                       render_kw={"placeholder": "Lviv weekend"})
    start_date = DayMonthYearField("From", validators=[DataRequired()])
    end_date = DayMonthYearField("To", validators=[DataRequired()])
    submit = SubmitField("Pack a suitcase")

    # WTForms calls validate_<field name> by itself, after the field's own
    # validators. It's the place for rules that need two fields at once.
    def validate_end_date(self, field):
        start = self.start_date.data
        if start and field.data:
            if field.data < start:
                raise ValidationError("The trip can't end before it starts.")
            if (field.data - start).days + 1 > MAX_TRIP_DAYS:
                raise ValidationError(f"That's more than {MAX_TRIP_DAYS} days. Check the year?")
