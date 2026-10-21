"""Laundry: a reminder when a plan uses clothes that are in the wash."""
from flask_babel import gettext as _
from flask_babel import ngettext


def wash_notice(items):
    """"Heads up: Blue jeans and White tee are in the wash." or None."""
    names = [item.name for item in items if item.in_wash]
    if not names:
        return None
    if len(names) == 1:
        what = names[0]
    else:
        what = _("%(names)s and %(last)s", names=", ".join(names[:-1]), last=names[-1])
    # ngettext picks "is" or "are" (Ukrainian has three forms, not two).
    return ngettext("Heads up: %(what)s is in the wash.", "Heads up: %(what)s are in the wash.",
                    len(names), what=what)
