"""Idea #4: fill in a wish from a shop link."""
import io
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from PIL import Image

from app.services import product_page
from app.services.product_page import FetchError, check_url, clean_price, extract_product
from tests.conftest import register
from tests.test_items import category_id, get_item

JSON_LD_PAGE = """
<html><head><title>Linen shirt | Shop</title>
<script type="application/ld+json">
{"@context": "https://schema.org", "@graph": [
  {"@type": "BreadcrumbList"},
  {"@type": ["Product"], "name": "Linen shirt",
   "image": ["/img/shirt-1.jpg", "/img/shirt-2.jpg"],
   "offers": [{"@type": "Offer", "price": "1299.90", "priceCurrency": "uah"}]}
]}
</script></head><body></body></html>
"""

OPEN_GRAPH_PAGE = """
<html><head>
<meta property="og:title" content="Wool coat">
<meta property="og:image" content="https://cdn.shop.com/coat.jpg">
<meta property="product:price:amount" content="89,95">
<meta property="product:price:currency" content="EUR">
</head></html>
"""


# ---------- reading pages ----------

def test_reads_json_ld_product():
    found = extract_product(JSON_LD_PAGE, "https://shop.com/p/123")
    assert found == {
        "name": "Linen shirt", "price": "1299.90", "currency": "UAH",
        "image_url": "https://shop.com/img/shirt-1.jpg",  # relative link made full
    }


def test_reads_open_graph_tags():
    found = extract_product(OPEN_GRAPH_PAGE, "https://shop.com/coat")
    assert found == {"name": "Wool coat", "price": "89.95", "currency": "EUR",
                     "image_url": "https://cdn.shop.com/coat.jpg"}


def test_falls_back_to_the_title_and_survives_broken_json():
    page = '<title> Plain page </title><script type="application/ld+json">{broken</script>'
    assert extract_product(page, "https://x.com")["name"] == "Plain page"


@pytest.mark.parametrize("text, expected", [
    ("1299.90", "1299.90"), ("1 299,90", "1299.90"), ("1,299.90", "1299.90"),
    (49, "49.00"), ("free", None), ("-5", None), (None, None),
])
def test_clean_price(text, expected):
    assert clean_price(text) == expected


# ---------- safety ----------

@pytest.mark.parametrize("url", [
    "ftp://shop.com/x", "javascript:alert(1)", "shop.com/no-scheme",
    "http://127.0.0.1:5000/admin", "http://localhost/", "http://192.168.1.1/",
])
def test_refuses_non_public_links(url):
    with pytest.raises(FetchError):
        check_url(url)


# ---------- the whole trip, against a tiny local "shop" ----------

PNG = io.BytesIO()
Image.new("RGB", (30, 60), "navy").save(PNG, "PNG")


class FakeShop(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/short":  # shops love redirects
            self.send_response(301)
            self.send_header("Location", "/product")
            self.end_headers()
        elif self.path == "/product":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(OPEN_GRAPH_PAGE.encode())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()
            self.wfile.write(PNG.getvalue())

    def log_message(self, *args):
        pass  # keep the test output quiet


@pytest.fixture
def shop(monkeypatch):
    # The fake shop runs on 127.0.0.1, which the safety check normally
    # refuses, so this one test allows it. Proxies are switched off too.
    monkeypatch.setattr(product_page, "is_public_address", lambda ip: True)
    for name in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
        monkeypatch.delenv(name, raising=False)
    server = HTTPServer(("127.0.0.1", 0), FakeShop)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_fetch_follows_redirects_and_reads_the_page(shop):
    found = product_page.fetch_product(shop + "/short")
    assert found["name"] == "Wool coat" and found["price"] == "89.95"


def test_api_answers_json(client, shop):
    register(client)
    response = client.post("/api/fetch-product", json={"url": shop + "/product"})
    assert response.status_code == 200
    assert response.get_json()["currency"] == "EUR"


def test_api_errors(client):
    register(client)
    assert client.post("/api/fetch-product", json={"url": ""}).status_code == 400
    response = client.post("/api/fetch-product", json={"url": "http://127.0.0.1/"})
    assert response.status_code == 422
    assert "public website" in response.get_json()["error"]


def test_saving_a_wish_downloads_the_shop_photo(client, shop):
    register(client)
    client.post("/items/wishlist/new", data={
        "name": "Wool coat", "category_id": category_id("Outerwear"), "color": "navy",
        "season": "winter", "style": "", "currency": "EUR", "priority": "0",
        "image_url": shop + "/coat.png",
    }, content_type="multipart/form-data")
    wish = get_item("Wool coat")
    assert wish.image_path and wish.image_path.startswith("items/")


def test_a_bad_shop_photo_link_is_reported(client):
    register(client)
    page = client.post("/items/wishlist/new", data={
        "name": "Wool coat", "category_id": category_id("Outerwear"), "color": "navy",
        "season": "winter", "style": "", "currency": "EUR", "priority": "0",
        "image_url": "http://127.0.0.1/secret.png",
    }, content_type="multipart/form-data", follow_redirects=True).get_data(as_text=True)
    assert "get the shop" in page
    assert get_item("Wool coat") is None
