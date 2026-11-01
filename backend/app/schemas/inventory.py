"""The inventory page's row, its header cards, and the two things it can change.

`is_low_stock` / `is_out_of_stock` are booleans, not a threshold the client
compares against: the rule belongs to the server, and v2's version of this page
fetched the settings singleton once per row to apply it.
"""

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from ..visibility import can_see_cost
from .category import CategoryRef
from .supplier import SupplierRef


class InventoryRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    sku: str
    name: str
    model_number: str
    unit: str
    supplier: SupplierRef | None = None
    category: CategoryRef | None = None
    quantity_on_hand: int
    quantity_reserved: int
    quantity_available: int
    is_low_stock: bool
    is_out_of_stock: bool
    stock_type: str = "stocked"


class InventorySummaryOut(BaseModel):
    total_products: int
    low_stock_count: int
    out_of_stock_count: int
    missing_supplier_count: int
    total_stock_value_paise: int | None

    @field_serializer("total_stock_value_paise")
    def _hide_cost(self, v: int | None) -> int | None:
        return v if can_see_cost() else None


class StockAdjustRequest(BaseModel):
    """A manual correction. Zero is refused by the stock service, not here,
    so the message the operator sees is the service's one."""

    model_config = ConfigDict(extra="forbid")

    # Bounded: a slip of extra zeros should be a form error, not a stock count.
    delta: int = Field(ge=-1_000_000, le=1_000_000)
    note: str = Field(default="", max_length=255)


class SupplierAssignRequest(BaseModel):
    """`null` clears the supplier — which is why it is a distinct model rather
    than a bare query parameter that cannot tell absent from null."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: int | None = None


__all__ = [
    "InventoryRowOut",
    "InventorySummaryOut",
    "StockAdjustRequest",
    "SupplierAssignRequest",
]
