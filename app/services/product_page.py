"""Idea #4: read name, price and photo from a shop's product page.

Most shops describe their products for link previews (when you paste a
link in a chat). Two common ways:

- Open Graph <meta> tags in the page head:
      <meta property="og:title" content="Linen shirt">
      <meta property="og:image" content="https://shop.com/shirt.jpg">
      <meta property="product:price:amount" content="1299.90">
- A JSON-LD block, structured data for search engines:
      <script type="application/ld+json">{"@type": "Product", "name": ..., "offers": {...}}</script>

We download the page, look for both and return what we found. It's a best
guess: some shops build their pages with JavaScript or block scripts, so
the user always checks the form before saving.

Only Python's standard library is used (urllib, html.parser, json), so
there is nothing new to install.
"""
import ipaddress
import json
import socket
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from flask_babel import gettext as _

TIMEOUT_SECONDS = 8
MAX_PAGE_BYTES = 3 * 1024 * 1024    # 3 MB of HTML is plenty
MAX_IMAGE_BYTES = 8 * 1024 * 1024
# Some shops refuse requests that don't look like a browser.
USER_AGENT = "Mozilla/5.0 (compatible; DigitalWardrobe/1.0; +autofill)"


class FetchError(Exception):
    """Something went wrong; the message is safe to show to the user."""


# ---------- Safety: only public web addresses ----------

def is_public_address(ip_text):
    """True for addresses on the open internet, False for 127.0.0.1, 192.168.x.x...

    Without this check, anyone could make the server open
    http://127.0.0.1/admin or a machine on your home network for them
    ("server-side request forgery").
    """
    return ipaddress.ip_address(ip_text).is_global


def check_url(url):
    """Refuse anything but a public http(s) link. Raise FetchError if not."""
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError(_("Paste a full link, starting with http:// or https://."))
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(parts.hostname, None)}
    except socket.gaierror:
        raise FetchError(_("That website doesn't seem to exist.")) from None
    if not all(is_public_address(address) for address in addresses):
        raise FetchError(_("That link doesn't point to a public website."))


class _CheckRedirects(HTTPRedirectHandler):
    """Shops often redirect (http -> https, short links). Check every hop too."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, max_bytes):
    """GET a URL. Return (bytes, content_type). Raise FetchError on any problem."""
    check_url(url)
    opener = build_opener(_CheckRedirects)
    request = Request(url, headers={"User-Agent": USER_AGENT,
                                    "Accept-Language": "en,uk;q=0.8"})
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            # Read one byte more than allowed, to notice a file that's too big.
            body = response.read(max_bytes + 1)
            content_type = response.headers.get("Content-Type", "")
    except FetchError:
        raise
    except (URLError, OSError, ValueError):
        raise FetchError(_("Couldn't open that page. Check the link, or fill the form in by hand.")) from None
    if len(body) > max_bytes:
        raise FetchError(_("That page or picture is too big."))
    return body, content_type


# ---------- Reading the page ----------

class _ProductParser(HTMLParser):
    """Collects <meta> tags, JSON-LD blocks and the <title> while reading the HTML."""

    def __init__(self):
        super().__init__()
        self.meta = {}       # "og:title" -> "Linen shirt"
        self.json_ld = []    # the text of every <script type="application/ld+json">
        self.title = ""
        self._in = None      # which tag's text we're collecting right now

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            if key and attrs.get("content") and key not in self.meta:
                self.meta[key] = attrs["content"].strip()
        elif tag == "script" and (attrs.get("type") or "").lower() == "application/ld+json":
            self._in = "json"
            self.json_ld.append("")
        elif tag == "title":
            self._in = "title"

    def handle_endtag(self, tag):
        if tag in ("script", "title"):
            self._in = None

    def handle_data(self, data):
        if self._in == "json":
            self.json_ld[-1] += data
        elif self._in == "title":
            self.title += data


def _find_product(data):
    """Search parsed JSON-LD (a dict, a list, or a dict with "@graph") for a Product."""
    if isinstance(data, list):
        for entry in data:
            found = _find_product(entry)
            if found:
                return found
    elif isinstance(data, dict):
        kind = data.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "Product" in kinds:
            return data
        if "@graph" in data:
            return _find_product(data["@graph"])
    return None


def _first(value):
    """JSON-LD may give one thing or a list of things; take the first."""
    return value[0] if isinstance(value, list) and value else value


def clean_price(text):
    """ "1 299,90" or "1,299.90" or 1299.9 -> "1299.90". Anything else -> None."""
    if text is None:
        return None
    text = str(text).replace(" ", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(",", "")         # 1,299.90 : comma separates thousands
    elif "," in text:
        text = text.replace(",", ".")        # 1299,90 : comma is the decimal point
    try:
        price = Decimal(text)
    except InvalidOperation:
        return None
    return f"{price:.2f}" if price >= 0 else None


def extract_product(html, page_url):
    """Read {name, price, currency, image_url} from a page's HTML. Missing -> None."""
    parser = _ProductParser()
    parser.feed(html)

    product = {}
    for block in parser.json_ld:
        try:
            product = _find_product(json.loads(block)) or {}
        except json.JSONDecodeError:
            continue  # a broken block on a real site; try the next one
        if product:
            break

    offer = _first(product.get("offers")) or {}
    if not isinstance(offer, dict):
        offer = {}
    image = _first(product.get("image"))
    if isinstance(image, dict):
        image = image.get("url")
    meta = parser.meta

    name = product.get("name") or meta.get("og:title") or parser.title.strip() or None
    price = clean_price(offer.get("price") or offer.get("lowPrice")
                        or meta.get("product:price:amount") or meta.get("og:price:amount"))
    currency = (offer.get("priceCurrency") or meta.get("product:price:currency")
                or meta.get("og:price:currency") or None)
    image = image or meta.get("og:image")

    return {
        "name": name[:100] if name else None,
        "price": price,
        "currency": currency.upper()[:3] if currency else None,
        # A relative link like "/img/shirt.jpg" becomes a full one.
        "image_url": urljoin(page_url, image) if image else None,
    }


def fetch_product(url):
    """Download a product page and read it. Raise FetchError if that fails."""
    body, content_type = download(url, MAX_PAGE_BYTES)
    # "text/html; charset=windows-1251" -> decode with that charset.
    charset = "utf-8"
    if "charset=" in content_type:
        charset = content_type.split("charset=")[-1].split(";")[0].strip() or "utf-8"
    try:
        html = body.decode(charset, errors="replace")
    except LookupError:  # a charset Python doesn't know
        html = body.decode("utf-8", errors="replace")
    found = extract_product(html, url)
    if not any(found.values()):
        raise FetchError(_("Couldn't find product details on that page. Fill the form in by hand."))
    return found


def download_image(url):
    """Download a product photo. Returns the bytes; Pillow checks them later."""
    body, _content_type = download(url, MAX_IMAGE_BYTES)
    return body
