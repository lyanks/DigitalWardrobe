from flask_babel import lazy_gettext as _l
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, Regexp

from app.dates import DayMonthYearField
from app.forms import BaseForm


class InviteForm(BaseForm):
    note = StringField(_l("Who is it for?"), validators=[Optional(), Length(max=100)],
                       description=_l("Only you see this."))
    expires_on = DayMonthYearField(_l("Works until"), validators=[Optional()],
                                   description=_l("Leave empty for no end date."))
    submit = SubmitField(_l("Make a code"))


# What the colour dot may be: "#3b6fd1", or a gradient made of the same
# safe characters (it goes into a style="" attribute, so nothing else).
SWATCH = r"^(#[0-9a-fA-F]{6}|linear-gradient\([0-9a-zA-Z#%,. ]+\))$"


class OptionForm(BaseForm):
    """Add or edit one category, colour, season, style or occasion.

    The route removes the fields a kind doesn't use: hex is only for
    colours, slot only for categories.
    """
    name = StringField(_l("Name in English"), validators=[DataRequired(), Length(max=20)])
    name_uk = StringField(_l("Name in Ukrainian"), validators=[Optional(), Length(max=50)],
                          description=_l("Shown when the app is in Ukrainian. Empty = the English name."))
    hex = StringField(_l("Colour of the dot"), validators=[
        DataRequired(), Regexp(SWATCH, message=_l("Write it like #3b6fd1.")),
    ], render_kw={"placeholder": "#3b6fd1"})
    slot = SelectField(_l("Where it's worn"), choices=[
        ("top", _l("Top")), ("bottom", _l("Bottom")), ("full", _l("Full body")),
        ("outer", _l("Outer layer")), ("feet", _l("Feet")), ("accessory", _l("Accessory")),
    ])
    submit = SubmitField(_l("Add"))
