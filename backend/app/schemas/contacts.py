"""Many emails and many phone numbers on a customer or supplier.

The lists are the source of truth; the old single `email` / `phone` columns
stay, always equal to the first list entry, because the quotation and purchase
order PDFs (and any client that has not caught up) still read them.

Old clients may still send a single `email` / `phone`. It is merged into the
list rather than rejected, so nothing that worked yesterday breaks today.
"""

import re
from typing import Any, Final

from email_validator import EmailNotValidError, validate_email

MAX_CONTACTS: Final = 10
PHONE_RE: Final = re.compile(r"^[0-9+\-() ]{7,20}$")


def _as_list(value: object, field: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"{field} must be a list of strings.")
    return list(value)


def clean_emails(values: list[str]) -> list[str]:
    """Trim, drop blanks, validate, dedupe (case-insensitively), cap."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        if not value:
            continue
        if len(value) > 255:
            raise ValueError(f"'{value[:40]}…' is too long for an email address.")
        try:
            validate_email(value, check_deliverability=False)
        except EmailNotValidError as exc:
            raise ValueError(f"'{value}' is not a valid email address.") from exc
        if value.lower() in seen:
            continue
        seen.add(value.lower())
        out.append(value)
    if len(out) > MAX_CONTACTS:
        raise ValueError(f"At most {MAX_CONTACTS} email addresses are allowed.")
    return out


def clean_phones(values: list[str]) -> list[str]:
    """Trim, drop blanks, validate, dedupe (by digits), cap."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = " ".join(raw.split())
        if not value:
            continue
        if not PHONE_RE.match(value):
            raise ValueError(
                f"'{value}' is not a valid phone number "
                "(7-20 characters: digits, spaces, +, -, brackets)."
            )
        key = re.sub(r"\D", "", value)
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    if len(out) > MAX_CONTACTS:
        raise ValueError(f"At most {MAX_CONTACTS} phone numbers are allowed.")
    return out


def merge_contacts(data: Any, *, partial: bool) -> Any:
    """`mode="before"` validator body shared by every create/update schema.

    When a list is sent, the legacy single value (if also sent) joins it and
    the single value is set to the first entry. On create, a legacy single
    value alone becomes a one-entry list. On update, a legacy single value
    alone is left for the service to splice into the stored list.
    """
    if not isinstance(data, dict):
        return data
    data = dict(data)
    for plural, single, clean in (
        ("emails", "email", clean_emails),
        ("phones", "phone", clean_phones),
    ):
        has_list = plural in data and data[plural] is not None
        has_single = single in data and data[single] is not None
        if not has_list and partial:
            if has_single:
                cleaned = clean(_as_list(data[single], single))
                data[single] = cleaned[0] if cleaned else ""
            continue
        values = _as_list(data.get(plural), plural)
        if has_single:
            values = [*values, *_as_list(data[single], single)]
        cleaned = clean(values)
        data[plural] = cleaned
        data[single] = cleaned[0] if cleaned else ""
    return data


def splice_first(existing: list[str], first: str) -> list[str]:
    """A legacy PATCH of the single value: replace the first list entry."""
    rest = [v for v in existing[1:] if v.lower() != first.lower()]
    return [first, *rest] if first else rest
