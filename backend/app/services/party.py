"""The rules a customer, a supplier and their branches share.

GST number, city, state and pin code are mandatory, the GST number must be a
well-formed GSTIN and the pin code six digits. They are enforced here, in the
create and update paths, and not in the request schemas, because the contact
importer builds the same schemas from someone else's spreadsheet and an
incomplete row there is still worth keeping (it is flagged, not refused).

Records saved before these rules existed may lack the fields. They keep
working: an update may leave an already-blank field blank, and a stored value
that is not touched is never re-judged. What an update may not do is blank a
field that has a value, and a value it does write must be well-formed. The
form asks for the missing ones on the next edit (`missing_required`).
"""

from typing import Any

from ..errors import ValidationFailed
from ..schemas.party import GSTIN_RE, PIN_RE


def validate_party(
    values: dict[str, Any], required: dict[str, str], *, stored: Any | None = None
) -> dict[str, Any]:
    """Normalise and check the mandatory fields in `values`; returns a copy.

    `stored` is the existing row on an update, None on a create. On a create
    every mandatory field must be given. On an update only the fields sent
    are looked at (see the module docstring for what a legacy blank may do).
    """
    out = dict(values)
    for field, label in required.items():
        if out.get(field) is None:
            if stored is None:
                raise ValidationFailed(f"{label} is required.", field=field)
            continue
        value = str(out[field]).strip()
        if field == "gstin":
            value = value.replace(" ", "").upper()
        out[field] = value
        old = "" if stored is None else (getattr(stored, field) or "").strip()
        if not value:
            if stored is None or old:
                raise ValidationFailed(f"{label} is required.", field=field)
            continue
        if stored is not None and value == old:
            continue
        if field == "gstin" and not GSTIN_RE.fullmatch(value):
            raise ValidationFailed(
                f"'{value}' is not a valid GST number (15 characters, e.g. 33AAIFE2328P1Z9).",
                field=field,
            )
        if field.endswith("pincode") and not PIN_RE.fullmatch(value):
            raise ValidationFailed(f"'{value}' is not a valid pin code (6 digits).", field=field)
    return out
