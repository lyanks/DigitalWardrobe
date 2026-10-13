"""BEHIND_PROXY: on the server, the Google callback link must be https://."""
from urllib.parse import parse_qs, urlparse

from app import create_app
from config import TestConfig


def _callback_url(config_class):
    client = create_app(config_class).test_client()
    # Pretend to be the PythonAnywhere proxy: it talks plain http to Flask
    # and adds headers saying what the phone really asked for.
    headers = {"X-Forwarded-Proto": "https", "X-Forwarded-Host": "me.pythonanywhere.com"}
    response = client.get("/login/google", headers=headers)
    # We're sent to Google with ?redirect_uri=<where Google sends us back>.
    query = parse_qs(urlparse(response.headers["Location"]).query)
    return query["redirect_uri"][0]


def test_proxy_headers_ignored_on_your_computer():
    assert _callback_url(TestConfig) == "http://localhost/login/google/callback"


def test_proxy_headers_trusted_on_the_server():
    class ServerConfig(TestConfig):
        BEHIND_PROXY = True

    assert _callback_url(ServerConfig) == "https://me.pythonanywhere.com/login/google/callback"
