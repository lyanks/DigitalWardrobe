"""Idea #7: the setup wizard after sign-up."""
from app.extensions import db
from app.models import GoalAnswer, User
from tests.conftest import google_invite, login, logout, register
from tests.test_auth import fake_google


def alice():
    return db.session.scalar(db.select(User).filter_by(username="alice"))


def goal_counts():
    rows = db.session.execute(
        db.select(GoalAnswer.goal, db.func.count()).group_by(GoalAnswer.goal)).all()
    return dict(rows)


def test_sign_up_opens_the_wizard(client):
    page = register(client, skip_setup=False).get_data(as_text=True)
    assert "What should we call you?" in page
    assert "Step 1 of 3" in page
    assert alice().onboarded_at is None


def test_walk_through_all_three_steps(client):
    register(client, skip_setup=False)
    response = client.post("/welcome/1", data={"username": "alice_k", "display_name": "Alice"})
    assert response.headers["Location"].endswith("/welcome/2")
    client.post("/welcome/2", data={"goals": ["buy_less", "track"]})
    page = client.post("/welcome/3", data={"theme": "linen", "accent_color": "#c4a8ff",
                                           "use_theme_accent": "y"},
                       follow_redirects=True).get_data(as_text=True)
    assert "All set!" in page
    user = db.session.scalar(db.select(User).filter_by(username="alice_k"))
    assert user.display_name == "Alice"
    assert goal_counts() == {"buy_less": 1, "track": 1}
    assert user.theme == "linen"
    assert user.onboarded_at is not None


def test_skip_a_step_saves_nothing(client):
    register(client, skip_setup=False)
    response = client.post("/welcome/1", data={"username": "", "skip": "1"})
    assert response.headers["Location"].endswith("/welcome/2")
    assert alice() is not None   # username unchanged, no "required" error


def test_username_rules_still_apply(client):
    register(client, username="bob", email="bob@example.com")
    logout(client)
    register(client, skip_setup=False)
    page = client.post("/welcome/1", data={"username": "bob"}).get_data(as_text=True)
    assert "That username is taken." in page


def test_unknown_goals_are_refused(client):
    register(client, skip_setup=False)
    client.post("/welcome/2", data={"goals": ["become_famous"]})
    assert goal_counts() == {}


def test_skip_the_whole_setup(client):
    register(client, skip_setup=False)
    page = client.post("/welcome/skip", follow_redirects=True).get_data(as_text=True)
    assert "All set!" in page
    assert alice().onboarded_at is not None


def test_login_goes_to_the_wizard_until_it_is_done(client):
    register(client, skip_setup=False)
    logout(client)
    assert "What should we call you?" in login(client).get_data(as_text=True)
    client.post("/welcome/skip")
    logout(client)
    assert "What should we call you?" not in login(client).get_data(as_text=True)


def test_new_google_account_gets_the_wizard(client, monkeypatch):
    fake_google(monkeypatch)
    google_invite(client)
    response = client.get("/login/google/callback")
    assert response.headers["Location"].endswith("/welcome")


def test_goals_are_anonymous_and_counted_once(client):
    register(client, skip_setup=False)
    client.post("/welcome/2", data={"goals": ["faster"]})
    client.post("/welcome/2", data={"goals": ["faster", "plan"]})   # went back, Next again
    assert goal_counts() == {"faster": 1}
    assert not hasattr(alice(), "goals")


def test_goals_are_not_on_the_profile(client):
    register(client)
    page = client.get("/profile").get_data(as_text=True)
    assert "Why you use the app" not in page
    assert "Get dressed faster" not in page


def test_flask_goals_prints_the_counts(app, client):
    register(client, skip_setup=False)
    client.post("/welcome/2", data={"goals": ["plan", "track"]})
    output = app.test_cli_runner().invoke(args=["goals"]).output
    assert "    1  Plan outfits ahead" in output
    assert "    0  Get dressed faster" in output


def test_wizard_needs_login_and_real_steps(client):
    assert client.get("/welcome/1").status_code == 302
    register(client)
    assert client.get("/welcome/4").status_code == 404
