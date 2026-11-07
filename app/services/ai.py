"""Talking to Claude (Anthropic's AI) from the server. No routes here.

One function, ask_claude(), sends a question (and maybe a picture) and
gets back JSON in the exact shape we asked for. Anything AI in the app
goes through it, so the key, the model, the time limit and the daily
limit live in one place.

Setup: put ANTHROPIC_API_KEY=sk-ant-... in .env (see .env.example).
Without a key, is_enabled() is False and the AI buttons are hidden.

Why the answer is reliable JSON: we pass a "JSON schema" (a description
of the shape: these keys, this one is a list of these words...) in
output_config. The API then guarantees the reply matches it, so the
code never has to guess what the model meant.
"""
import base64
import json
from datetime import date

from flask import current_app
from flask_babel import gettext as _

from app.extensions import db


class AiError(Exception):
    """Something went wrong; the message is safe to show to the user."""


def is_enabled():
    return bool(current_app.config.get("ANTHROPIC_API_KEY"))


def daily_limit():
    from app.guests import is_guest
    config = current_app.config
    return config["AI_GUEST_DAILY_LIMIT"] if is_guest() else config["AI_DAILY_LIMIT"]


def use_quota(user_id):
    """Count one AI request for today, or raise AiError over the limit.

    Each request costs real money (a tenth of a cent), so a bug or a
    curious friend pressing the button 1,000 times can't run up a bill.
    """
    from app.models import AiUsage
    today = date.today()
    row = db.session.get(AiUsage, (user_id, today))  # primary key: (user, day)
    if row is None:
        row = AiUsage(user_id=user_id, day=today, count=0)
        db.session.add(row)
    if row.count >= daily_limit():
        raise AiError(_("That's all the AI help for today. It's back tomorrow."))
    row.count += 1
    db.session.commit()


def _client():
    # Imported here, so the rest of the app (and the tests) run even
    # where the anthropic package isn't installed yet.
    import anthropic
    # timeout in seconds; max_retries: the SDK tries once more by itself
    # after a network error or an overloaded server.
    return anthropic.Anthropic(api_key=current_app.config["ANTHROPIC_API_KEY"],
                               timeout=30.0, max_retries=1)


def ask_claude(prompt, schema, image_bytes=None, media_type="image/jpeg", max_tokens=2048):
    """Ask Claude and return its answer as a dict shaped like `schema`.

    image_bytes: an optional picture (JPEG/PNG bytes) to look at.
    Raises AiError with a friendly message if anything fails.
    """
    import anthropic
    if not is_enabled():
        raise AiError(_("AI suggestions are switched off on this server."))

    content = []
    if image_bytes:
        content.append({
            "type": "image",
            # The picture goes inside the request as base64: bytes written
            # as plain letters, because JSON can only carry text.
            "source": {"type": "base64", "media_type": media_type,
                       "data": base64.standard_b64encode(image_bytes).decode("ascii")},
        })
    content.append({"type": "text", "text": prompt})

    try:
        response = _client().messages.create(
            model=current_app.config["AI_MODEL"],
            max_tokens=max_tokens,
            # effort "low": a quick look is enough for tagging, and cheaper.
            output_config={"effort": "low",
                           "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.RateLimitError as error:
        raise AiError(_("The AI is busy right now. Try again in a minute.")) from error
    except anthropic.APIConnectionError as error:  # includes timeouts
        raise AiError(_("Couldn't reach the AI. Try again.")) from error
    except anthropic.APIStatusError as error:  # any other answer with an error code
        current_app.logger.warning("Claude API error %s: %s", error.status_code, error.message)
        raise AiError(_("The AI couldn't answer. Try again later.")) from error

    if response.stop_reason in ("refusal", "max_tokens"):
        raise AiError(_("The AI couldn't answer. Try again later."))
    text = next((block.text for block in response.content if block.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise AiError(_("The AI couldn't answer. Try again later.")) from error
