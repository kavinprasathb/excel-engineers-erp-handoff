"""Quotations, in and out.

A quote is edited as one document: PATCH carries the header, every line and
every term together, and the server replaces lines and terms wholesale. Per-
line endpoints would mean per-line races and a save button per row; the
editor is one form, so the API is one body.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..constants import LineKind, QuotationStatus, QuotationType, VersionKind
from .customer import CustomerBranchRef, CustomerRef


class Deviation(BaseModel):
    """One `label : value` row of an item's technical deviation."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=100)
    value: str = Field(default="", max_length=2000)


class Component(BaseModel):
    """One inventory item of a multi-item line, and how many go into one of its units."""

    model_config = ConfigDict(extra="forbid")

    product_id: int
    name: str = Field(default="", max_length=300)
    quantity: int = Field(default=1, gt=0, le=1_000_000)


class TechRow(BaseModel):
    """One row of the technical sheet: its section heading and parameter."""

    model_config = ConfigDict(extra="forbid")

    section: str = Field(default="", max_length=100)
    label: str = Field(min_length=1, max_length=150)


QuotationFormat = Literal["pump", "spares", "technical"]
PrintColumn = Literal["part_no", "moc", "unit", "delivery"]


def _default_columns() -> list[PrintColumn]:
    """A spares offer prints MOC and Unit unless switched off."""
    return ["moc", "unit"]


class LineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: LineKind = LineKind.PRODUCT
    unit_label: str = Field(default="Each", max_length=30)
    hsn_code: str = Field(default="", max_length=15)
    product_id: int | None = None
    description: str = Field(min_length=1, max_length=2000)
    quantity: int = Field(default=1, gt=0)
    # Any rate at all. The client negotiates below list price and the app
    # must not second-guess that; there is no floor.
    rate_paise: int = Field(default=0, ge=0)
    # The item's technical deviation rows. Omitted means "start from the
    # default rows"; a note never has any.
    deviations: list[Deviation] | None = None
    # Several inventory items in one line; their stock moves per item.
    components: list[Component] = Field(default_factory=list, max_length=50)
    # Technical sheet only: the column heading and one value per tech row.
    service: str = Field(default="", max_length=150)
    tech_values: list[str] = Field(default_factory=list, max_length=200)
    part_no: str = Field(default="", max_length=60)
    moc: str = Field(default="", max_length=60)
    delivery: str = Field(default="", max_length=60)
    supply_scope: str = Field(default="", max_length=2000)


class LineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    kind: LineKind
    unit_label: str
    hsn_code: str
    product_id: int | None
    description: str
    quantity: int
    rate_paise: int
    value_paise: int
    deviations: list[Deviation]
    components: list[Component]
    service: str
    tech_values: list[str]
    part_no: str
    moc: str
    delivery: str
    supply_scope: str


class TermIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=100)
    text: str = Field(max_length=2000)
    included: bool = True


class TermOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    label: str
    text: str
    included: bool


class QuotationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: QuotationType
    customer_id: int
    # One of the customer's branches, or none: the head office.
    customer_branch_id: int | None = None
    quote_date: date
    subject: str = Field(default="", max_length=255)
    reference: str = Field(default="", max_length=255)
    notes: str = ""
    format: QuotationFormat = "pump"
    print_columns: list[PrintColumn] = Field(default_factory=_default_columns)
    tech_rows: list[TechRow] = Field(default_factory=list, max_length=200)
    scope: str = Field(default="", max_length=4000)
    price_label: str = Field(default="", max_length=150)
    lines: list[LineIn] = Field(default_factory=list)
    # Omitted means "start from the defaults for this type".
    terms: list[TermIn] | None = None


class QuotationUpdate(BaseModel):
    """Header fields optional; lines/terms, when sent, replace the existing set."""

    model_config = ConfigDict(extra="forbid")

    customer_id: int | None = None
    # Sent as null to address the head office. A new customer without a
    # branch sent clears it, so a branch never outlives its customer here.
    customer_branch_id: int | None = None
    quote_date: date | None = None
    subject: str | None = Field(default=None, max_length=255)
    reference: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    format: QuotationFormat | None = None
    print_columns: list[PrintColumn] | None = None
    tech_rows: list[TechRow] | None = Field(default=None, max_length=200)
    scope: str | None = Field(default=None, max_length=4000)
    price_label: str | None = Field(default=None, max_length=150)
    lines: list[LineIn] | None = None
    terms: list[TermIn] | None = None


class StatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: QuotationStatus
    # Mandatory for `declined`, ignored otherwise. Enforced in the service so
    # the message names the rule, not a schema field.
    reason: str = Field(default="", max_length=2000)


class ReviseIn(BaseModel):
    """Which kind of version to start. Omitted body: a negotiation, as before."""

    model_config = ConfigDict(extra="forbid")

    kind: VersionKind = VersionKind.NEGOTIATION


class ChangeOut(BaseModel):
    section: str
    item: str
    field: str
    before: str
    after: str


class LineChangeOut(BaseModel):
    description: str
    old_quantity: int | None
    new_quantity: int | None
    old_rate_paise: int | None
    new_rate_paise: int | None
    change: str  # kept | added | removed


class CompareOut(BaseModel):
    changes: list[ChangeOut]
    lines: list[LineChangeOut]


class ItemSuggestion(BaseModel):
    """Something quoted before that matches the description being typed."""

    description: str
    details: str
    part_no: str
    moc: str
    unit: str
    rate_paise: int
    hsn_code: str
    offer_no: str
    offer_date: date | None
    customer_name: str
    # Quoted to the customer of the quotation being written.
    same_customer: bool
    # "past offer" (from the letters) or "quotation" (made in the app).
    source: str


class HistoryStage(BaseModel):
    """One version after the original, in the order they were made."""

    label: str  # "R1", "N2", "R2N1"
    rate_paise: int | None


class HistoryRow(BaseModel):
    quotation_id: int
    number: str
    customer: str
    description: str
    quantity: int | None
    quoted_paise: int | None
    # Exactly ten: N1..N10. None = that stage does not exist / item absent.
    # Kept for older clients; `stages` is the same, labelled R or N.
    negotiations_paise: list[int | None]
    # Every version after the original, labelled: revised and negotiated prices.
    stages: list[HistoryStage]
    # The latest revised quotation's price, before any negotiation of it.
    revised_paise: int | None
    # The latest version's price: what the deal stands at now.
    current_paise: int | None
    original_number: str
    stage: int
    stage_label: str
    status: QuotationStatus
    decline_reason: str
    quote_date: date


class DashboardRow(BaseModel):
    id: int
    number: str
    customer: str
    stage: int
    stage_label: str
    status: QuotationStatus
    quote_date: date
    updated_at: datetime
    total_paise: int
    decline_reason: str


class DashboardBucket(BaseModel):
    count: int
    total_paise: int


class DashboardOut(BaseModel):
    buckets: dict[str, DashboardBucket]
    awaiting: list[DashboardRow]
    negotiating: list[DashboardRow]
    accepted: list[DashboardRow]
    declined: list[DashboardRow]


class QuotationSummary(BaseModel):
    """A list row. No lines or terms; the total is enough."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    type: QuotationType
    revision: int
    # R of the revised quotation this version belongs to (0: the original),
    # and N of its negotiation round (0: not a negotiation).
    rev_no: int
    neg_no: int
    # The original quotation's number, and "Revision R2 · Negotiation N1".
    base_number: str
    stage_label: str
    format: str
    created_at: datetime
    customer: CustomerRef
    quote_date: date
    subject: str
    status: QuotationStatus
    total_paise: int
    updated_at: datetime


class QuotationOut(QuotationSummary):
    customer_branch: CustomerBranchRef | None
    reference: str
    notes: str
    decline_reason: str
    supersedes_id: int | None
    # True only for the highest revision of its number — the one that may be
    # edited, revised, accepted or declined.
    is_latest: bool
    print_columns: list[str]
    tech_rows: list[TechRow]
    scope: str
    price_label: str
    lines: list[LineOut]
    terms: list[TermOut]


__all__ = [
    "ChangeOut",
    "CompareOut",
    "Component",
    "DashboardOut",
    "Deviation",
    "HistoryRow",
    "ItemSuggestion",
    "LineChangeOut",
    "LineIn",
    "LineOut",
    "QuotationCreate",
    "QuotationOut",
    "QuotationSummary",
    "QuotationUpdate",
    "ReviseIn",
    "StatusChange",
    "TechRow",
    "TermIn",
    "TermOut",
]
