"""What a customer, a supplier and their branches must carry.

The checks themselves run in `services.party`; this module holds the
patterns and the field labels, and says which mandatory fields a stored
record is still missing so the screens can flag it for completion.
"""

import re
from typing import Any, Final

GSTIN_RE: Final = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]")
PIN_RE: Final = re.compile(r"\d{6}")

# field -> label, for the main records and for branches.
CUSTOMER_REQUIRED: Final = {
    "gstin": "GST Number",
    "billing_city": "City",
    "billing_state": "State",
    "billing_pincode": "Pin Code",
}
PARTY_REQUIRED: Final = {
    "gstin": "GST Number",
    "city": "City",
    "state": "State",
    "pincode": "Pin Code",
}


def missing_required(record: Any, required: dict[str, str]) -> list[str]:
    """The labels of the mandatory fields this record has left blank."""
    return [
        label for field, label in required.items() if not (getattr(record, field) or "").strip()
    ]
