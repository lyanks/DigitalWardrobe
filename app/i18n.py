"""Languages: English and Ukrainian (Flask-Babel).

How a translated page works:
1. Every text a person reads is wrapped: _("Add item") in templates and
   Python. In English, _() just gives the text back.
2. `pybabel extract` collects all wrapped texts into one list, and the
   Ukrainian file app/translations/uk/LC_MESSAGES/messages.po pairs each
   one with its translation:
       msgid "Add item"
       msgstr "Додати річ"
3. On each request get_locale() decides the language, and _() looks the
   text up in that language's file.

The .po file is the one you edit. The app reads a compiled copy of it
(messages.mo); compile_translations() below rebuilds that copy whenever
the .po file is newer, so you never have to do it by hand.
"""
import os

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po
from flask import request, session
from flask_babel import format_date as babel_format_date
from flask_babel import gettext
from flask_login import current_user

# code -> what the switch in the header shows. "uk" is the language code
# for Ukrainian ("ua" is the country).
LANGUAGES = {"en": "EN", "uk": "UA"}
DEFAULT_LANGUAGE = "en"


def get_locale():
    """The language for this request, in this order:
    1. what a logged-in user picked (saved on their account),
    2. what a visitor picked (saved in the session cookie),
    3. what their browser asks for (the Accept-Language header),
    4. English.
    """
    if current_user.is_authenticated and current_user.language in LANGUAGES:
        return current_user.language
    if session.get("language") in LANGUAGES:
        return session["language"]
    return request.accept_languages.best_match(LANGUAGES) or DEFAULT_LANGUAGE


def N_(text):
    """Marks a text for translation without translating it yet.

    For words stored in the database or in fixed lists (category names,
    colours...): pybabel finds them here, and templates translate them
    when they're shown, with the | tr filter.
    """
    return text


def tr(text):
    """The | tr filter: {{ item.category.name | tr }} -> "Верх"."""
    return gettext(text) if text else text


# Words that come from the database or fixed lists, so pybabel can find them.
DATA_WORDS = [
    # categories (seed.py)
    N_("Tops"), N_("Bottoms"), N_("Dresses"), N_("Outerwear"), N_("Shoes"), N_("Accessories"),
    # colours (wardrobe/choices.py)
    N_("black"), N_("white"), N_("grey"), N_("beige"), N_("brown"), N_("navy"), N_("blue"),
    N_("light blue"), N_("green"), N_("olive"), N_("yellow"), N_("orange"), N_("red"),
    N_("burgundy"), N_("pink"), N_("purple"), N_("multicolor"),
    # seasons
    N_("all"), N_("spring"), N_("summer"), N_("autumn"), N_("winter"),
    # styles
    N_("casual"), N_("formal"), N_("business"), N_("sporty"), N_("streetwear"), N_("classic"),
    N_("party"), N_("home"),
    # occasions (the ones not already above)
    N_("work"), N_("date"), N_("sport"), N_("travel"),
    # wishlist priorities
    N_("Must have"), N_("Would be nice"), N_("Someday"),
    # themes
    N_("Midnight"), N_("Graphite"), N_("Lavender"), N_("Linen"),
    # why you use the app (goals.py)
    N_("Plan outfits ahead"), N_("Buy less, wear more of what I have"),
    N_("Track what I actually wear"), N_("Get dressed faster"),
    N_("Sell or donate what I don't wear"),
]


# ---------- dates with names in them ----------
# Numbers stay dd.mm.yyyy (app/dates.py). Only day and month *names* need a
# language, and Babel knows them for every language.

def weekday(day):
    """"Wednesday" / "середа"."""
    return babel_format_date(day, "EEEE")


def weekday_short(day):
    """"Wed" / "ср"."""
    return babel_format_date(day, "EEE")


def month_name(day):
    """"October" / "жовтень" (the form used on its own, as a title)."""
    return babel_format_date(day, "LLLL")


def month_year(day):
    """"October 2026" / "Жовтень 2026"."""
    return babel_format_date(day, "LLLL y").capitalize()


# ---------- texts used by JavaScript ----------
# The scripts can't call _(), so base.html puts these into the page as
# JSON and the scripts use t("..."), which looks the English text up.
JS_TEXTS = [
    N_("Couldn't save that. Try again."),
    N_("Couldn't save that."),
    N_("Couldn't reach the server. Try again."),
    N_("Already in the suitcase."),
    N_("Empty"),
    N_("%(packed)s of %(count)s packed"),
    N_("Couldn't put that in the wash. Try again."),
    N_("In the wash"),
    N_("Are you sure?"),
    N_("Cancel"),
    N_("Delete"),
    N_("Saving…"),
    N_("Order saved."),
    N_("Couldn't save the new order. Reloading…"),
    N_("Planned “%(name)s” for %(date)s."),
    N_("Looks like a complete outfit ✓"),
    N_("Paste a link first."),
    N_("Looking at the page…"),
    N_("name"), N_("price"), N_("photo"),
    N_("Filled in: %(fields)s. Check it, then pick a category and colour."),
    N_("The price is in %(currency)s, which isn't in the list."),
    N_("The page had no details we could read. Fill the form in by hand."),
    N_("Something went wrong. Try again, or fill the form in by hand."),
    N_("Show password"), N_("Hide password"),
    N_("Copied: %(text)s"), N_("Couldn't copy. Select the code and copy it by hand."),
]


def js_texts():
    """{English: translated} for every text in JS_TEXTS."""
    return {text: gettext(text) for text in JS_TEXTS}


# ---------- keeping messages.mo up to date ----------

def compile_translations(app):
    """Rebuild each messages.mo from its messages.po when the .po is newer."""
    folder = os.path.join(app.root_path, "translations")
    for language in os.listdir(folder) if os.path.isdir(folder) else []:
        po_path = os.path.join(folder, language, "LC_MESSAGES", "messages.po")
        mo_path = po_path[:-3] + ".mo"
        if not os.path.exists(po_path):
            continue
        if os.path.exists(mo_path) and os.path.getmtime(mo_path) >= os.path.getmtime(po_path):
            continue
        with open(po_path, "rb") as po_file:
            catalog = read_po(po_file, locale=language)
        with open(mo_path, "wb") as mo_file:
            write_mo(mo_file, catalog)
