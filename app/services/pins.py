"""Read the picture and title from a Pinterest pin (or any web page).

Why not the official Pinterest API? It needs an approved developer app,
an OAuth login for every user, and approval is slow and often refused for
small personal apps. A pin page, like most pages, describes itself for
link previews (what you see when you paste a link in a chat):

    <meta property="og:image" content="https://i.pinimg.com/736x/ab/cd/ef.jpg">
    <meta property="og:title" content="Autumn outfit idea">

So we download the page and read those tags, with the same safe
downloader and HTML reader the shop autofill uses (product_page.py).
That also means any page with a preview picture works, not only pins.
"""
from urllib.parse import urljoin, urlparse

from flask_babel import gettext as _

from app.services.product_page import MAX_PAGE_BYTES, FetchError, _ProductParser, download

TITLE_LENGTH = 200


def _decode(body, content_type):
    charset = "utf-8"
    if "charset=" in content_type:
        charset = content_type.split("charset=")[-1].split(";")[0].strip() or "utf-8"
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def read_pin(html, page_url):
    """{"title", "image_url"} from a page's HTML. Missing -> None."""
    parser = _ProductParser()
    parser.feed(html)
    meta = parser.meta
    image = meta.get("og:image") or meta.get("og:image:url") or meta.get("twitter:image")
    title = (meta.get("og:title") or meta.get("og:description")
             or meta.get("description") or parser.title.strip() or None)
    image_url = urljoin(page_url, image) if image else None
    # Only web pictures: never "javascript:" or "data:" in an <img src>.
    if image_url and urlparse(image_url).scheme not in ("http", "https"):
        image_url = None
    return {"title": title[:TITLE_LENGTH] if title else None, "image_url": image_url}


def fetch_pin(url):
    """Download a pin page and read it. Raise FetchError if there's no picture."""
    body, content_type = download(url, MAX_PAGE_BYTES)
    found = read_pin(_decode(body, content_type), url)
    if not found["image_url"]:
        raise FetchError(_("Couldn't find a picture on that page. Save the picture and upload it instead."))
    return found
