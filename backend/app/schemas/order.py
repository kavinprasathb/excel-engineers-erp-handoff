"""Orders and purchase orders, out (and the little that goes in)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer

from ..constants import OrderStatus, PurchaseOrderStatus
from ..visibility import can_see_cost
from .customer import CustomerRef
from .supplier import SupplierBranchRef


class OrderLineOut(BaseModel):
    id: int
    product_id: int
    sku: str
    description: str
    quantity: int
    # Held in stock for this order; `short` is what is still to come.
    reserved: int
    short: int
    rate_paise: int
    # The line's worth: quantity x rate, or for an item of a set, the set's
    # value on its first item and 0 on the rest.
    value_paise: int
    # For an item of a set: the set as quoted ("Pump, Base Frame, Coupling").
    set_description: str


class OrderOut(BaseModel):
    id: int
    number: str
    status: OrderStatus
    quotation_id: int
    quotation_number: str
    customer: CustomerRef
    delivered_at: datetime | None
    created_at: datetime
    total_paise: int
    lines: list[OrderLineOut]


class SupplierRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class PurchaseOrderLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    description: str
    quantity: int
    rate_paise: int | None
    gst_rate_bp: int

    @field_serializer("rate_paise")
    def _hide_cost(self, v: int | None) -> int | None:
        return v if can_see_cost() else None


class PurchaseOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    status: PurchaseOrderStatus
    sent_at: datetime | None
    received_at: datetime | None
    supplier: SupplierRef | None
    supplier_branch: SupplierBranchRef | None
    order_id: int | None
    created_at: datetime
    lines: list[PurchaseOrderLineOut]


class SetSupplier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: int
    # One of the supplier's branches, or none: the head office.
    branch_id: int | None = None


__all__ = [
    "OrderLineOut",
    "OrderOut",
    "PurchaseOrderLineOut",
    "PurchaseOrderOut",
    "SetSupplier",
    "SupplierRef",
]
