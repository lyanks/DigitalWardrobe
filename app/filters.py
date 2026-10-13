"""Small Jinja filters: how prices, shop links and colours look."""
from urllib.parse import urlparse

from app.wardrobe.choices import COLORS


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


def swatch(color_name):
    """"blue" -> "#3b6fd1", the colour used for that name's dot. Unknown -> grey."""
    return COLORS.get(color_name, "#9a9a9a")
