"""A reusable WTForms validator for strong passwords."""
import string

from wtforms.validators import ValidationError

# Each rule: (what is missing, a function that checks the password).
RULES = [
    ("at least 8 characters", lambda p: len(p) >= 8),
    ("a lowercase letter", lambda p: any(c.islower() for c in p)),
    ("an uppercase letter", lambda p: any(c.isupper() for c in p)),
    ("a number", lambda p: any(c.isdigit() for c in p)),
    ("a special character like ! ? # @ $", lambda p: any(c in string.punctuation for c in p)),
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
        missing = missing_rules(field.data)
        if missing:
            # ["a", "b", "c"] -> "a, b and c"
            if len(missing) > 1:
                text = ", ".join(missing[:-1]) + " and " + missing[-1]
            else:
                text = missing[0]
            raise ValidationError(f"Password needs {text}.")
