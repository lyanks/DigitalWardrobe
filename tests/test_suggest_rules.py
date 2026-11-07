"""The "Suggest a look" rules (services/suggest.py), with fake items."""
import random
from datetime import date
from types import SimpleNamespace

import pytest

from app.services.suggest import body_points, color_points, season_of, suggest

SLOTS = {"tee": "top", "shirt": "top", "jeans": "bottom", "skirt": "bottom",
         "dress": "full", "coat": "outer", "boots": "feet"}


def fake(item_id, name, color, seasons=(), moods=(), worn=0, washing=False):
    """Just enough of an Item: the fields and methods suggest() reads."""
    slot = SLOTS[name.split()[-1]]
    return SimpleNamespace(
        id=item_id, name=name, color=color, times_worn=worn, in_wash=washing,
        category=SimpleNamespace(slot=slot), moods=list(moods),
        fits_season=lambda season, s=tuple(seasons): not s or season in s,
    )


@pytest.fixture(autouse=True)
def page(app):
    """The reasons are translated, which needs a request (in English here)."""
    with app.test_request_context():
        yield


@pytest.fixture
def wardrobe():
    return [
        fake(1, "white tee", "white"),
        fake(2, "red shirt", "red"),
        fake(3, "blue jeans", "navy"),
        fake(4, "pink skirt", "pink"),
        fake(5, "black dress", "black", seasons=["summer"]),
        fake(6, "wool coat", "beige", seasons=["autumn", "winter"]),
        fake(7, "black boots", "black"),
    ]


def test_season_of():
    assert season_of(date(2026, 1, 15)) == "winter"
    assert season_of(date(2026, 11, 7)) == "autumn"
    assert season_of(date(2026, 7, 1)) == "summer"


def test_neutrals_score_better_than_a_clash():
    calm, _ = color_points(["white", "navy", "black"])
    loud, reasons = color_points(["red", "pink"])
    assert calm > loud
    assert any("clash" in reason for reason in reasons)


def test_pear_likes_light_top_dark_bottom():
    top, bottom = fake(1, "white tee", "white"), fake(2, "blue jeans", "navy")
    assert body_points([top, bottom], "pear")[0] > 0
    assert body_points([top, bottom], "inverted")[0] == 0
    assert body_points([top, bottom], None)[0] == 0


def test_suggest_gives_valid_different_looks(wardrobe):
    looks = suggest(wardrobe, "autumn", rng=random.Random(1))
    assert looks
    tops = [next(i.id for i in look.items if i.category.slot in ("top", "full")) for look in looks]
    assert len(tops) == len(set(tops))           # never the same top twice
    for look in looks:
        slots = [i.category.slot for i in look.items]
        assert "feet" in slots and "outer" in slots  # boots, and a coat in autumn
        assert 5 not in look.item_ids                  # summer dress is out of season


def test_best_look_avoids_the_clash(wardrobe):
    best = suggest(wardrobe, "autumn", rng=random.Random(2))[0]
    assert not {2, 4} <= set(best.item_ids)     # red shirt + pink skirt


def test_clothes_in_the_wash_are_skipped(wardrobe):
    wardrobe[0].in_wash = True
    for look in suggest(wardrobe, "autumn", rng=random.Random(3)):
        assert 1 not in look.item_ids


def test_worn_this_week_is_pushed_down(wardrobe):
    recent = [{1, 3}]  # white tee + jeans, worn this week
    best = suggest(wardrobe, "autumn", recent=recent, rng=random.Random(4))[0]
    assert not {1, 3} <= set(best.item_ids)


def test_mood_wins(wardrobe):
    wardrobe[1].moods = ["classy"]   # red shirt
    wardrobe[3].moods = ["classy"]   # pink skirt (clashes, but both classy)
    wardrobe[0].moods = ["home"]
    best = suggest(wardrobe, "autumn", moods=["classy"], rng=random.Random(5))[0]
    assert 2 in best.item_ids
    assert "Fits the mood you picked." in best.reasons


def test_empty_wardrobe():
    assert suggest([], "summer") == []


# ---------- weather and learning ----------

def test_weather_decides_the_jacket():
    from app.services.suggest import needs_jacket
    assert needs_jacket("summer", {"temp": 9})          # cold summer day: jacket
    assert not needs_jacket("winter", {"temp": 24})     # warm winter day: none
    assert needs_jacket("autumn", {"temp": 18})         # in between: the season decides
    assert not needs_jacket("spring", None)


def test_warm_day_leaves_the_coat_at_home(wardrobe):
    for look in suggest(wardrobe, "autumn", weather={"temp": 25, "rain": 0}, rng=random.Random(6)):
        assert 6 not in look.item_ids


def test_rain_prefers_dark_shoes(wardrobe):
    from app.services.suggest import rain_points
    white = fake(8, "white boots", "white")
    assert rain_points([white], {"temp": 10, "rain": 80})[0] < 0
    assert rain_points([wardrobe[6]], {"temp": 10, "rain": 80})[0] > 0
    assert rain_points([white], {"temp": 10, "rain": 10})[0] == 0


def test_learning_from_votes(wardrobe):
    from app.services.suggest import learned_points
    tee, jeans, shirt = wardrobe[0], wardrobe[2], wardrobe[1]
    liked = [({1, 3, 7}, True)]
    disliked = [({1, 3, 7}, False)]
    assert learned_points([tee, jeans], liked)[0] > 0
    assert learned_points([tee, jeans], disliked)[0] < -5     # the same look, turned down
    assert learned_points([shirt, wardrobe[3]], disliked)[0] == 0  # nothing shared


def test_not_for_me_changes_the_top_look(wardrobe):
    first = suggest(wardrobe, "autumn", rng=random.Random(7))[0]
    votes = [(set(first.item_ids), False)]
    again = suggest(wardrobe, "autumn", votes=votes, rng=random.Random(7))[0]
    assert set(again.item_ids) != set(first.item_ids)
