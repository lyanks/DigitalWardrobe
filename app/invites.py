"""Invite codes: making them, checking them and using them up.

A code looks like WARD-7KQ2-M9XD. The letters leave out 0/O and 1/I/L,
so a code read out loud or copied by hand can't be mistaken.
"""
import re
import secrets
from datetime import date

from app.extensions import db
from app.models import InviteCode, utcnow

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def new_code():
    """A random code nobody has yet. `secrets` (not `random`) can't be predicted."""
    while True:
        part = lambda: "".join(secrets.choice(ALPHABET) for _ in range(4))  # noqa: E731
        code = f"WARD-{part()}-{part()}"
        if not db.session.scalar(db.select(InviteCode).filter_by(code=code)):
            return code


def create_invite(note=None, expires_on=None):
    invite = InviteCode(code=new_code(), note=note or None, expires_on=expires_on)
    db.session.add(invite)
    db.session.commit()
    return invite


def tidy(text):
    """What someone typed -> the stored form: " ward 7kq2m9xd" -> "WARD-7KQ2-M9XD"."""
    letters = re.sub(r"[^A-Za-z0-9]", "", text or "").upper()
    if len(letters) == 12:
        return f"{letters[:4]}-{letters[4:8]}-{letters[8:]}"
    return letters


def find_usable(text):
    """The InviteCode for this text if it can still be used, otherwise None."""
    invite = db.session.scalar(db.select(InviteCode).filter_by(code=tidy(text)))
    if invite and invite.status(date.today()) == "waiting":
        return invite
    return None


def use_invite(invite, user):
    """Mark the code as used by this (just added) user. False if someone was faster.

    The UPDATE only changes the row while used_at is still empty. If two
    people send the same code at the same moment, only the first UPDATE
    changes a row, and the second sees rowcount 0.
    """
    db.session.flush()  # gives the new user its id
    result = db.session.execute(
        db.update(InviteCode)
        .where(InviteCode.id == invite.id, InviteCode.used_at.is_(None),
               InviteCode.disabled_at.is_(None))
        .values(used_at=utcnow(), used_by_id=user.id)
    )
    return result.rowcount == 1
