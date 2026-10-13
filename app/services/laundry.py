"""Laundry: a reminder when a plan uses clothes that are in the wash."""


def wash_notice(items):
    """"Heads up: Blue jeans and White tee are in the wash." or None."""
    names = [item.name for item in items if item.in_wash]
    if not names:
        return None
    what = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    verb = "is" if len(names) == 1 else "are"
    return f"Heads up: {what} {verb} in the wash."
