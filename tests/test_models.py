from app.models import User


def test_password_is_hashed_not_stored():
    user = User(username="bob", email="bob@example.com")
    user.set_password("hunter22")

    assert user.password_hash != "hunter22"
    assert user.check_password("hunter22")
    assert not user.check_password("wrong")


def test_shown_name_falls_back_to_username():
    user = User(username="bob", email="bob@example.com")
    assert user.shown_name == "bob"
    user.display_name = "Bobby"
    assert user.shown_name == "Bobby"
