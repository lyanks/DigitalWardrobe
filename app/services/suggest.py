"""Suggest a look from your own wardrobe, with rules (no AI, free).

How it works, in four steps:
1. Candidates: every top with every bottom, plus every dress / full-body
   item. Only clean clothes that fit the season.
2. Score each one. Every rule adds or takes away points and, when it
   matters, leaves a short reason ("Navy goes with everything").
3. Finish the best ones: add the shoes that go best with them, and a
   jacket when it's cold.
4. Pick the top few, never two looks with the same top, bottom or dress.

The rules are plain Python sets and if-statements, on purpose: you can
read every one of them, change the numbers and see what happens. The
functions take plain objects, not the database, so the tests can call
them with fakes.

Undertone and body shape come from the profile and are optional. They
only add a few points; they never hide anything.
"""
import random
from dataclasses import dataclass, field
from itertools import product

from flask_babel import gettext as _

from app.i18n import N_, tr
from app.services.combo_check import combo_ids
from app.services.outfit_rules import outfit_problems, sort_by_slot

# ---------- colours ----------

# Go with everything.
NEUTRALS = {"black", "white", "grey", "beige", "navy", "brown"}

# Pairs most people find loud together. frozenset: the order doesn't matter.
CLASHES = {frozenset(pair) for pair in [
    ("red", "pink"), ("red", "orange"), ("orange", "pink"),
    ("red", "green"), ("purple", "orange"), ("multicolor",),
]}

# For the "lighter on top / darker below" rules of body shapes.
LIGHT = {"white", "beige", "light blue", "yellow", "pink", "grey"}
DARK = {"black", "navy", "brown", "burgundy", "olive"}

# Colours that usually flatter each skin undertone, worn near the face.
UNDERTONE_COLORS = {
    "warm": {"beige", "brown", "olive", "orange", "yellow", "red", "green", "burgundy"},
    "cool": {"navy", "blue", "light blue", "grey", "pink", "purple", "white", "burgundy"},
    "neutral": set(),  # most colours work: no bonus, no penalty
}

UNDERTONES = {
    "warm": N_("Warm"),
    "cool": N_("Cool"),
    "neutral": N_("Neutral"),
}

BODY_SHAPES = {
    "pear": N_("Hips wider than shoulders"),
    "inverted": N_("Shoulders wider than hips"),
    "hourglass": N_("Shoulders and hips even, defined waist"),
    "rectangle": N_("Shoulders, waist and hips about even"),
    "round": N_("Fuller around the middle"),
}

# Slots near the face: the undertone rule looks at these.
FACE_SLOTS = {"top", "full", "outer"}
COLD_SEASONS = {"autumn", "winter"}

# The biggest wardrobe still gets an answer fast: at most this many
# top + bottom pairs are scored (a random sample of them).
MAX_CANDIDATES = 600


@dataclass
class Suggestion:
    items: list
    score: float = 0.0
    reasons: list = field(default_factory=list)

    @property
    def item_ids(self):
        return [item.id for item in self.items]


def season_of(day):
    """date -> "winter" / "spring" / "summer" / "autumn"."""
    return {12: "winter", 1: "winter", 2: "winter",
            3: "spring", 4: "spring", 5: "spring",
            6: "summer", 7: "summer", 8: "summer"}.get(day.month, "autumn")


def _slot(item):
    return item.category.slot


# ---------- the scoring rules ----------

def color_points(colors):
    """Points for how a set of colours goes together, and the reasons."""
    colors = [c for c in colors if c]
    loud = {c for c in colors if c not in NEUTRALS}
    points, reasons = 0, []
    for clash in CLASHES:
        # ("multicolor",) means "two multicolour pieces".
        hit = colors.count("multicolor") > 1 if len(clash) == 1 else clash <= loud
        if hit:
            points -= 3
            reasons.append(_("%(colors)s can clash.", colors=" + ".join(tr(c) for c in sorted(clash))))
    if len(loud) <= 1:
        points += 2
        reasons.append(_("Calm colours: at most one bright piece."))
    elif len(loud) > 2:
        points -= 1
    return points, reasons


def undertone_points(items, undertone):
    flattering = UNDERTONE_COLORS.get(undertone or "", set())
    near_face = [item for item in items if _slot(item) in FACE_SLOTS and item.color in flattering]
    if not near_face:
        return 0, []
    return 2, [_("%(color)s near your face suits your undertone (%(undertone)s).",
                 color=tr(near_face[0].color).capitalize(), undertone=_(UNDERTONES[undertone]).lower())]


def body_points(items, shape):
    """Simple balance rules: light and bright draw the eye, dark calms it."""
    by_slot = {_slot(item): item for item in items}
    top, bottom = by_slot.get("top"), by_slot.get("bottom")
    if shape == "hourglass" and "full" in by_slot:
        return 1, [_("A dress follows your waist.")]
    if shape == "round" and "outer" in by_slot:
        return 1, [_("An open layer makes a long line.")]
    if not (top and bottom):
        return 0, []
    if shape == "pear" and top.color in LIGHT and bottom.color in DARK:
        return 2, [_("Lighter on top, darker below: balances the hips.")]
    if shape == "inverted" and top.color in DARK and bottom.color in LIGHT:
        return 2, [_("Darker on top, lighter below: balances the shoulders.")]
    if shape == "rectangle" and (top.color in LIGHT) != (bottom.color in LIGHT):
        return 1, [_("Contrast between top and bottom shapes the waist.")]
    if shape == "round" and top.color == bottom.color:
        return 1, [_("One colour top to bottom makes a long line.")]
    return 0, []


def mood_points(items, moods):
    """+2 for each piece in a mood you picked, -2 for a piece in another mood."""
    if not moods:
        return 0, []
    points, matched = 0, []
    for item in items:
        tagged = set(item.moods)
        if tagged & moods:
            points += 2
            matched.append(item)
        elif tagged:
            points -= 2
    reasons = [_("Fits the mood you picked.")] if matched else []
    return points, reasons


def freshness_points(items, median_worn):
    """Prefer clothes you wear less than usual."""
    rare = [item for item in items if item.times_worn < median_worn]
    if not rare:
        return 0, []
    return 0.5 * len(rare), [_("Gives %(name)s more wear.", name=rare[0].name)]


def recent_points(items, recent):
    """recent: a list of sets of item ids, one per day of the last week."""
    combo = combo_ids(items)
    if combo and any(combo <= day for day in recent):
        return -5, [_("You wore this combination this week.")]
    return 0, []


def score(items, profile):
    """Add up every rule. profile: a dict made by suggest() below."""
    total, reasons = 0.0, []
    for points, why in (
        color_points([item.color for item in items]),
        undertone_points(items, profile["undertone"]),
        body_points(items, profile["body_shape"]),
        mood_points(items, profile["moods"]),
        freshness_points(items, profile["median_worn"]),
        recent_points(items, profile["recent"]),
    ):
        total += points
        reasons.extend(why)
    return total, reasons


# ---------- putting it together ----------

def _best_addition(base, choices, profile):
    """The piece from `choices` that makes `base` score highest, or None."""
    best, best_score = None, None
    for choice in choices:
        points, _reasons = score(base + [choice], profile)
        if best_score is None or points > best_score:
            best, best_score = choice, points
    return best


def suggest(items, season, moods=(), undertone=None, body_shape=None, recent=(),
            count=3, rng=None):
    """Up to `count` Suggestions, best first.

    items: the user's owned clothes. Ones in the wash or out of season
    are skipped here. rng: a random.Random, so "Shuffle" gives other
    looks and the tests can fix the seed.
    """
    rng = rng or random.Random()
    usable = [item for item in items if not item.in_wash and item.fits_season(season)]
    by_slot = {}
    for item in usable:
        by_slot.setdefault(_slot(item), []).append(item)

    worn = sorted(item.times_worn for item in usable) or [0]
    profile = {"undertone": undertone, "body_shape": body_shape, "moods": set(moods),
               "median_worn": worn[len(worn) // 2], "recent": list(recent)}

    bases = [[top, bottom] for top, bottom in product(by_slot.get("top", []), by_slot.get("bottom", []))]
    if len(bases) > MAX_CANDIDATES:
        bases = rng.sample(bases, MAX_CANDIDATES)
    bases += [[dress] for dress in by_slot.get("full", [])]

    scored = []
    for base in bases:
        points, _reasons = score(base, profile)
        # A little randomness, less than one point, so equal looks take
        # turns and "Shuffle" shows something new.
        scored.append((points + rng.random() * 0.9, base))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    picked, used = [], set()
    for _points, base in scored:
        key_ids = {item.id for item in base}
        if key_ids & used:
            continue  # one look per top, bottom and dress
        look = list(base)
        if season in COLD_SEASONS and by_slot.get("outer"):
            look.append(_best_addition(look, by_slot["outer"], profile))
        if by_slot.get("feet"):
            look.append(_best_addition(look, by_slot["feet"], profile))
        if outfit_problems(look):
            continue
        points, reasons = score(look, profile)
        picked.append(Suggestion(items=sort_by_slot(look), score=points, reasons=reasons))
        used |= key_ids
        if len(picked) == count:
            break
    return picked
