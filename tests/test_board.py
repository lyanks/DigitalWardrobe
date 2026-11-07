"""The outfit board: where each item sits in the Pinterest-style collage."""
import json
from types import SimpleNamespace

from app.services.outfit_board import board_pieces, default_spot, parse_layout
from tests.conftest import register
from tests.test_outfits import get_outfit, ids, make_basics, save_outfit


# ---------- the plain-Python part ----------

def test_default_spots_follow_the_body():
    top, bottom, feet = default_spot("top"), default_spot("bottom"), default_spot("feet")
    assert top["y"] < bottom["y"] < feet["y"]          # head to toe
    assert default_spot("outer")["layer"] > top["layer"] > feet["layer"]  # jacket over the top


def test_accessories_go_down_a_column():
    first, second = default_spot("accessory", 0), default_spot("accessory", 1)
    assert first["x"] == second["x"] and second["y"] > first["y"]


def test_parse_layout_keeps_only_good_pieces():
    sent = json.dumps({
        "1": {"x": 10, "y": 20, "width": 30, "layer": 2},
        "2": {"x": 999, "y": -999, "width": 0.5, "layer": 5},   # clamped
        "3": {"x": 1, "y": 1, "width": 30, "layer": 1},         # not your item
        "4": {"x": "left", "y": 1, "width": 30, "layer": 1},    # not a number
        "oops": {},
    })
    layout = parse_layout(sent, allowed_ids={1, 2, 4})
    assert layout == {
        1: {"x": 10, "y": 20, "width": 30, "layer": 2},
        2: {"x": 100, "y": -50, "width": 5, "layer": 5},
    }


def test_parse_layout_survives_rubbish():
    assert parse_layout("not json", {1}) == {}
    assert parse_layout("[1, 2]", {1}) == {}
    assert parse_layout(None, {1}) == {}
    assert parse_layout('{"1": {"x": NaN, "y": 1, "width": 9, "layer": 1}}', {1}) == {}


def test_board_pieces_use_saved_spots_and_go_back_to_front():
    def link(slot, saved=None):
        x, y, width, layer = saved or (None, None, None, None)
        item = SimpleNamespace(category=SimpleNamespace(slot=slot))
        return SimpleNamespace(item=item, board_x=x, board_y=y, board_width=width, board_layer=layer)
    shoes, top = link("feet"), link("top", (5, 6, 50, 0))
    pieces = board_pieces([top, shoes])
    assert pieces[0][0] is top.item and pieces[0][1] == {"x": 5, "y": 6, "width": 50, "layer": 0}
    assert pieces[1][1] == default_spot("feet")


# ---------- saving with the outfit ----------

def test_layout_is_saved_with_the_outfit(client):
    register(client)
    make_basics(client)
    tee, jeans = ids("White tee", "Blue jeans")
    layout = {str(tee): {"x": 12.5, "y": 3, "width": 55, "layer": 7}}
    save_outfit(client, item_ids=[tee, jeans], layout=json.dumps(layout))
    links = {link.item_id: link for link in get_outfit("Weekend").item_links}
    assert (links[tee].board_x, links[tee].board_width, links[tee].board_layer) == (12.5, 55, 7)
    assert links[jeans].board_x is None  # never moved: the board uses its default spot

    page = client.get(f"/outfits/{get_outfit('Weekend').id}").get_data(as_text=True)
    assert "left: 12.5%; top: 3.0%; width: 55.0%; z-index: 7" in page


def test_editing_without_javascript_keeps_the_layout(client):
    register(client)
    make_basics(client)
    tee, jeans = ids("White tee", "Blue jeans")
    save_outfit(client, item_ids=[tee, jeans], layout=json.dumps({str(tee): {"x": 1, "y": 2, "width": 40, "layer": 3}}))
    outfit = get_outfit("Weekend")
    save_outfit(client, url=f"/outfits/{outfit.id}/edit", item_ids=[tee, jeans], name="Weekend")  # no layout sent
    assert {link.item_id: link.board_x for link in get_outfit("Weekend").item_links}[tee] == 1


def test_form_has_a_piece_for_every_item(client):
    register(client)
    make_basics(client)
    page = client.get("/outfits/new").get_data(as_text=True)
    assert page.count('class="board-piece" data-item-id=') == 4
    assert 'name="layout"' in page and "outfit_board.js" in page


def test_a_rejected_form_keeps_the_pieces_where_you_put_them(client):
    register(client)
    make_basics(client)
    (tee,) = ids("White tee")
    page = save_outfit(client, item_ids=[tee], layout=json.dumps({str(tee): {"x": 33, "y": 44, "width": 20, "layer": 1}}))
    page = page.get_data(as_text=True)
    assert "a top and a bottom" in page  # not saved: no bottom
    assert "left: 33.0%; top: 44.0%; width: 20.0%" in page


def test_outfit_list_shows_the_board(client):
    register(client)
    make_basics(client)
    save_outfit(client, item_ids=ids("White tee", "Blue jeans"))
    assert 'class="board board-mini"' in client.get("/outfits").get_data(as_text=True)
