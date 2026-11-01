"""Single source of truth for the app's enumerations.

Every member here becomes a Pydantic field type, therefore an OpenAPI enum,
therefore a TypeScript union in `frontend/src/api/generated.ts`. Nothing in this
file is ever retyped by hand on the frontend — v2 kept three copies in sync
manually and they drifted.
"""

from enum import StrEnum


class StockType(StrEnum):
    """How a product is kept.

    stocked: held on the shelf; low-stock alerts apply.
    to_order: quoted and sold, but bought in only when an order needs it
    (0 on the shelf is normal, so no low-stock alert; a short order still
    drafts a purchase order). service: labour, transport, service charges;
    never stocked, never reserved or delivered from stock.
    """

    STOCKED = "stocked"
    TO_ORDER = "to_order"
    SERVICE = "service"


class MovementType(StrEnum):
    """Why stock changed. Every StockMovement row carries one."""

    ADJUST = "adjust"  # manual correction: damage, recount, opening balance
    RECEIVE = "receive"  # goods in: purchase order receipt, new product stock
    RESERVE = "reserve"  # an order has claimed stock it has not yet taken
    RELEASE = "release"  # that claim was given back (order cancelled or reduced)
    DELIVER = "deliver"  # goods out: reserved stock physically left the shop
    IMPORT = "import"  # opening balance set by a spreadsheet import


class ReferenceType(StrEnum):
    """What caused a movement, so history can be traced back to its document."""

    MANUAL = "manual"
    IMPORT = "import"
    ORDER = "order"
    PURCHASE_ORDER = "purchase_order"
    CHALLAN = "challan"


class ImportJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in (ImportJobStatus.COMPLETED, ImportJobStatus.FAILED)


class UserRole(StrEnum):
    ADMIN = "admin"
    STAFF = "staff"  # defined and enforceable, but unused in slice 1


DEFAULT_UNIT = "piece"
UNITS: tuple[str, ...] = ("piece", "set", "meter", "kg", "litre", "box", "nos")

# A stock import may not sit "running" forever if the API restarts mid-job;
# anything older than this is marked failed on startup so pollers terminate.
IMPORT_STALE_MINUTES = 30

# Per-job cap on stored error detail. `error_count` still reports the true total.
IMPORT_MAX_STORED_ERRORS = 200


class QuotationType(StrEnum):
    """Which family a quote belongs to. Decides its number prefix and its
    default terms - the client runs one sequence per family today."""

    PUMPS = "pumps"
    VALVES = "valves"
    SPARES = "spares"


QUOTATION_PREFIXES: dict[QuotationType, str] = {
    QuotationType.PUMPS: "ESQP",
    QuotationType.VALVES: "ESQV",
    QuotationType.SPARES: "ESQSP",
}


class VersionKind(StrEnum):
    """What a new version of a quotation is for. A *revision* (R1, R2...)
    changes products, quantities or technical details; a *negotiation*
    (N1, N2...) changes prices only."""

    REVISION = "revision"
    NEGOTIATION = "negotiation"


class LineKind(StrEnum):
    """A quotation row is a priced product or a free note between them
    ("KSB Make", "Fitted with Mechanical Seal")."""

    PRODUCT = "product"
    NOTE = "note"


class QuotationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    # An older revision of a quote that has since been revised. Read-only.
    SUPERSEDED = "superseded"


# Terms a new quote starts with, per family, copied from the client's own
# letters (ESQSP-26-70 for spares; the pump and valve offers for the others).
# Each is a checkbox on the quote; the admin edits these in Settings.
_COMMON_TERMS: list[dict[str, str]] = [
    {"label": "Price Basis", "text": "The prices quoted are FOR Salem, Exclusive of GST"},
    {"label": "GST", "text": "GST @ 18% will be charged extra to your account"},
    {"label": "Delivery", "text": "2 weeks"},
    {"label": "Packing & Forwarding", "text": "Included on the above price"},
    {"label": "Freight", "text": "Actual to your account."},
    {"label": "Payment terms", "text": "Against Proforma Invoice"},
]
_VALIDITY = {"label": "Validity", "text": "30 days from date of this offer."}

# The technical deviation rows every new item line starts with, values blank.
# Only the rows given a value print, under that item.
DEFAULT_QUOTATION_SPECS: list[dict[str, str]] = [
    {"label": "Pump Model", "value": ""},
    {"label": "Liquid Handled", "value": ""},
    {"label": "Capacity (Cub.M/hr)", "value": ""},
    {"label": "Total Head (Mtrs)", "value": ""},
    {"label": "Shaft Seal", "value": ""},
    {"label": "Recommended Motor (kW)", "value": ""},
]
DEFAULT_QUOTATION_TERMS: dict[str, list[dict[str, str]]] = {
    QuotationType.PUMPS.value: [
        *_COMMON_TERMS,
        {
            "label": "Warranty",
            "text": "12 months from date of commissioning or 18 months from date of "
            "despatch, whichever is earlier, as per KSB policy",
        },
        _VALIDITY,
    ],
    QuotationType.VALVES.value: [
        *_COMMON_TERMS,
        {"label": "Warranty", "text": "12 months from date of despatch as per manufacturer policy"},
        _VALIDITY,
    ],
    QuotationType.SPARES.value: [
        *_COMMON_TERMS,
        {"label": "Warranty", "text": "No Warranty / Guarantee for spares as per KSB Policy"},
        _VALIDITY,
    ],
}


class OrderStatus(StrEnum):
    """Where an order made from an accepted quotation stands.

    The whole order waits until every item is in stock: the client ships an
    order complete or not at all.
    """

    WAITING_STOCK = "waiting_stock"
    READY = "ready"  # every item held in stock; ready for Product Delivery
    DELIVERED = "delivered"


class PurchaseOrderStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    RECEIVED = "received"


# Why a customer said no, as the decline dialog offers them. The reason is
# stored as the label, or "Other: <text>"; analytics counts by label.
DECLINE_REASONS = (
    "Price too high",
    "Lost to competitor",
    "Delivery time too long",
    "Project cancelled or on hold",
    "No response from customer",
    "Specification not matching",
)
