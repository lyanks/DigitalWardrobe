"""A reusable WTForms validator for strong passwords."""
import string

from flask_babel import gettext as _
from wtforms.validators import ValidationError

from app.i18n import N_

# Each rule: (what is missing, a function that checks the password).
# N_() only marks the label for translation; it is translated when shown.
RULES = [
    (N_("at least 8 characters"), lambda p: len(p) >= 8),
    (N_("a lowercase letter"), lambda p: any(c.islower() for c in p)),
    (N_("an uppercase letter"), lambda p: any(c.isupper() for c in p)),
    (N_("a number"), lambda p: any(c.isdigit() for c in p)),
    (N_("a special character like ! ? # @ $"), lambda p: any(c in string.punctuation for c in p)),
]


def missing_rules(password):
    """Return the list of rules the password doesn't meet (empty = strong)."""
    return [label for label, check in RULES if not check(password or "")]


class StrongPassword:
    """Use like any built-in validator: validators=[DataRequired(), StrongPassword()].

    A validator is just a callable that gets (form, field) and raises
    ValidationError when something is wrong. A class with __call__ is
    one way to write that.
    """

    def __call__(self, form, field):
        missing = [_(label) for label in missing_rules(field.data)]
        if missing:
            # ["a", "b", "c"] -> "a, b and c"
            if len(missing) > 1:
                text = _("%(first)s and %(last)s", first=", ".join(missing[:-1]), last=missing[-1])
            else:
                text = missing[0]
            raise ValidationError(_("Password needs %(rules)s.", rules=text))
