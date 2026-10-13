"""How dates look in this app: day.month.year, e.g. 14.10.2026.

Every date a person reads or types goes through here, so changing the
format later is a one-line change. Machines keep the ISO format
(2026-10-14): URLs, the JSON API and data-date attributes, because it
sorts correctly and every library understands it.
"""
from datetime import date, datetime

from wtforms import DateField
from wtforms.widgets import TextInput

DATE_FORMAT = "%d.%m.%Y"
# What people may type: dots, slashes or dashes between day, month, year.
INPUT_FORMATS = [DATE_FORMAT, "%d/%m/%Y", "%d-%m-%Y"]


def format_date(value):
    """date(2026, 10, 14) -> "14.10.2026". None -> ""."""
    return value.strftime(DATE_FORMAT) if value else ""


def parse_date(text):
    """"14.10.2026" (or ISO "2026-10-14") -> a date. Anything else -> None."""
    text = (text or "").strip()
    for fmt in INPUT_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


class DayMonthYearField(DateField):
    """A date typed as dd.mm.yyyy.

    A browser's built-in date picker (<input type="date">) always shows the
    format of the browser's language (mm/dd/yyyy for US English), and a
    page can't change that. So this is a plain text box that reads
    14.10.2026, and also accepts / or - instead of the dots.
    """

    widget = TextInput()

    def __init__(self, label=None, validators=None, **kwargs):
        kwargs.setdefault("format", INPUT_FORMATS)
        kwargs.setdefault("render_kw", {"placeholder": "dd.mm.yyyy", "inputmode": "numeric"})
        super().__init__(label, validators, **kwargs)

    def process_formdata(self, valuelist):
        # Ignore spaces around what was typed, then try each format.
        valuelist = [value.strip() for value in valuelist]
        try:
            super().process_formdata(valuelist)
        except ValueError:
            raise ValueError("Write the date as dd.mm.yyyy, e.g. 14.10.2026.")
