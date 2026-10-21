from flask_babel import lazy_gettext as _l
from wtforms import SelectMultipleField, SubmitField
from wtforms.widgets import CheckboxInput, ListWidget

from app.auth.forms import LookForm, ProfileForm
from app.forms import BaseForm
from app.goals import GOALS


class NameForm(ProfileForm):
    """Step 1: username and display name.

    It inherits everything from the profile page's form (the same username
    rules, the "already taken" check), and setting a field to None in a
    subclass removes it, so there's no avatar upload here.
    """
    avatar = None
    submit = SubmitField(_l("Next"))


class MultiCheckboxField(SelectMultipleField):
    """Several ticked boxes instead of a multi-select list (WTForms recipe)."""
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class GoalsForm(BaseForm):
    """Step 2 (and the profile page): why you use the app. Pick any number."""
    # The labels are fixed English texts (goals.py); _l() shows each one
    # in the page's language when the checkboxes are drawn.
    goals = MultiCheckboxField(_l("Why do you use Digital Wardrobe?"),
                               choices=[(key, _l(label)) for key, label in GOALS.items()])
    submit = SubmitField(_l("Next"))


class WelcomeLookForm(LookForm):
    """Step 3: the theme picker from the profile page."""
    submit = SubmitField(_l("Finish"))


class SkipForm(BaseForm):
    """Only the CSRF token, for "Skip the setup"."""
