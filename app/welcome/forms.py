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
    submit = SubmitField("Next")


class MultiCheckboxField(SelectMultipleField):
    """Several ticked boxes instead of a multi-select list (WTForms recipe)."""
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class GoalsForm(BaseForm):
    """Step 2 (and the profile page): why you use the app. Pick any number."""
    goals = MultiCheckboxField("Why do you use Digital Wardrobe?",
                               choices=list(GOALS.items()))
    submit = SubmitField("Next")


class WelcomeLookForm(LookForm):
    """Step 3: the theme picker from the profile page."""
    submit = SubmitField("Finish")


class SkipForm(BaseForm):
    """Only the CSRF token, for "Skip the setup"."""
