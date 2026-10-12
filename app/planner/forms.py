from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from app.dates import DayMonthYearField


class ScheduleForm(FlaskForm):
    # The route fills the choices with the user's own outfits.
    outfit_id = SelectField("Outfit", coerce=int, validators=[DataRequired()])
    # Turns "14.10.2026" into a Python date object (see app/dates.py).
    date = DayMonthYearField("Day", validators=[DataRequired()])
    note = StringField("Note", validators=[Optional(), Length(max=200)])
    submit = SubmitField("Add to calendar")
