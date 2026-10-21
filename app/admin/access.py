"""Who may open the admin pages: only the account whose email is ADMIN_EMAIL.

Never a guest: a guest's account lives in their throwaway database, and
its email is made up, but the check says "not a guest" outright anyway.
"""
from flask import current_app


def is_admin(user):
    """True only for the logged-in account with the email in ADMIN_EMAIL (.env)."""
    from app.guests import is_guest
    wanted = current_app.config.get("ADMIN_EMAIL")
    return bool(
        wanted
        and user.is_authenticated
        and not is_guest()
        and (user.email or "").lower() == wanted
    )
