from flask_babel import lazy_gettext as _l
from wtforms import StringField, SubmitField
from wtforms.validators import Length, Optional

from app.dates import DayMonthYearField
from app.forms import BaseForm


class InviteForm(BaseForm):
    note = StringField(_l("Who is it for?"), validators=[Optional(), Length(max=100)],
                       description=_l("Only you see this."))
    expires_on = DayMonthYearField(_l("Works until"), validators=[Optional()],
                                   description=_l("Leave empty for no end date."))
    submit = SubmitField(_l("Make a code"))
