"""Who may open the admin pages: only the account whose email is ADMIN_EMAIL."""
from flask import current_app


def is_admin(user):
    """True only for the logged-in account with the email in ADMIN_EMAIL (.env)."""
    wanted = current_app.config.get("ADMIN_EMAIL")
    return bool(
        wanted
        and user.is_authenticated
        and (user.email or "").lower() == wanted
    )
