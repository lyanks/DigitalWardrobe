"""The new look: dark public pages, and the dark look stays off once you log in."""
from tests.conftest import register


def test_landing_page_for_visitors(client):
    page = client.get("/").get_data(as_text=True)
    assert 'class="public"' in page
    assert "thoughtfully" in page
    assert "Get started free" in page


def test_google_button_only_when_configured(app, client):
    app.config["GOOGLE_CLIENT_ID"] = ""
    assert "Continue with Google" not in client.get("/").get_data(as_text=True)
    app.config["GOOGLE_CLIENT_ID"] = "fake-id"
    assert "Continue with Google" in client.get("/").get_data(as_text=True)
    assert "Continue with Google" in client.get("/login").get_data(as_text=True)


def test_login_and_signup_are_dark_with_password_eye(client):
    for url, eyes in (("/login", 1), ("/register", 2)):
        page = client.get(url).get_data(as_text=True)
        assert 'class="public"' in page
        assert page.count("data-toggle-password") == eyes
        assert "password_toggle.js" in page


def test_logged_in_home_is_not_dark(client):
    register(client)
    page = client.get("/").get_data(as_text=True)
    assert 'class="public"' not in page
    assert "Get started free" not in page
