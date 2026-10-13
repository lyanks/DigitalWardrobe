"""Small Jinja filters for the wishlist: how prices and shop links look."""
from urllib.parse import urlparse


def format_price(amount, currency=None):
    """Decimal("1299.90"), "UAH" -> "1 299.90 UAH". Whole numbers drop ".00"."""
    if amount is None:
        return ""
    text = f"{amount:,.2f}".replace(",", " ")  # a space between thousands
    if text.endswith(".00"):
        text = text[:-3]
    return f"{text} {currency}" if currency else text


def shop_name(url):
    """"https://www.zara.com/ua/en/shirt-p123.html" -> "zara.com"."""
    host = urlparse(url).netloc.lower()
    return host.removeprefix("www.") or url
