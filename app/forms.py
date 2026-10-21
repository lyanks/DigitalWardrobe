"""The base class for every form in the app.

People often type a space at the end without seeing it ("my_name "). A
WTForms *filter* changes the value right after it arrives and before the
validators look at it, so here every text field gets one that strips the
spaces at both ends. Passwords are left alone: a space there is on purpose.
"""
from flask_wtf import FlaskForm
from wtforms import PasswordField


def strip_spaces(value):
    """" my_name " -> "my_name". Anything that isn't text stays as it is."""
    return value.strip() if isinstance(value, str) else value


class BaseForm(FlaskForm):
    class Meta:
        def bind_field(self, form, unbound_field, options):
            # Runs once for every field when a form is created.
            if not issubclass(unbound_field.field_class, PasswordField):
                filters = unbound_field.kwargs.get("filters", ())
                options["filters"] = [strip_spaces, *filters]
            return unbound_field.bind(form=form, **options)
