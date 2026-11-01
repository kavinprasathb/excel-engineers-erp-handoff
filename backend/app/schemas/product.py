"""Products and the stock ledger entries that explain their counters.

Money is integer paise and GST is basis points, everywhere, with no formatting
applied server-side — see docs/api-contract.md. A float here would reintroduce
exactly the rounding drift `values.to_paise` exists to prevent.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from ..constants import DEFAULT_UNIT, MovementType, ReferenceType, StockType
from ..visibility import can_see_cost
from .category import CategoryRef
from .supplier import SupplierRef

# Mirrors the CHECK constraints on `products`; the database is still the
# authority, this only turns a 500 into a 422 with a usable message.
MAX_PAISE = 10**15
MAX_GST_BP = 10000


class InventoryEmbed(BaseModel):
    """The counters as they appear nested inside a product.

    `quantity_available` is sent, never derived by the client: it is a
    generated column in Postgres and subtracting it in TypeScript is how three
    definitions of "available" got to disagree in v2.
    """

    model_config = ConfigDict(from_attributes=True)

    quantity_on_hand: int
    quantity_reserved: int
    quantity_available: int


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    model_number: str
    description: str
    unit: str
    hsn_code: str
    purchase_cost: int | None

    @field_serializer("purchase_cost")
    def _hide_cost(self, v: int | None) -> int | None:
        return v if can_see_cost() else None

    sell_price: int
    gst_rate_bp: int
    is_active: bool
    stock_type: StockType
    supplier: SupplierRef | None = None
    category: CategoryRef | None = None
    inventory: InventoryEmbed


class ProductLookup(BaseModel):
    """`/products/lookup` — what an item picker needs, nothing else.

    `purchase_cost` is deliberately absent: a customer-facing document screen
    must never be able to show what we paid, and the safest way to guarantee
    that is for the field never to leave the server on this path. `sell_price`
    is the list price, and `quantity_available` is read from the generated
    column so the picker can warn about stock without a second call.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    model_number: str
    unit: str
    hsn_code: str
    sell_price: int
    quantity_available: int
    stock_type: StockType = StockType.STOCKED


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Blank: the next SKU for the type is given (ITM-0001, ORD-0001, SRV-0001),
    # so an item can be added from a quotation without inventing one.
    sku: str = Field(default="", max_length=100)
    name: str = Field(min_length=1, max_length=255)
    model_number: str = Field(default="", max_length=120)
    description: str = ""
    unit: str = Field(default=DEFAULT_UNIT, min_length=1, max_length=20)
    hsn_code: str = Field(default="", max_length=15)
    supplier_id: int | None = None
    category_id: int | None = None
    purchase_cost: int = Field(default=0, ge=0, le=MAX_PAISE)
    sell_price: int = Field(default=0, ge=0, le=MAX_PAISE)
    gst_rate_bp: int = Field(default=0, ge=0, le=MAX_GST_BP)
    is_active: bool = True
    stock_type: StockType = StockType.STOCKED
    # The only stock a product may ever receive through this endpoint. Every
    # later change goes through /inventory, so there is one audited path.
    opening_quantity: int = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    """No quantity field of any kind, on purpose.

    PATCH /products must never move stock: a catalogue edit that silently
    rewrote the counters would leave the ledger unable to explain them.
    """

    model_config = ConfigDict(extra="forbid")

    sku: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    model_number: str | None = Field(default=None, max_length=120)
    description: str | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    hsn_code: str | None = Field(default=None, max_length=15)
    supplier_id: int | None = None
    category_id: int | None = None
    stock_type: StockType | None = None
    purchase_cost: int | None = Field(default=None, ge=0, le=MAX_PAISE)
    sell_price: int | None = Field(default=None, ge=0, le=MAX_PAISE)
    gst_rate_bp: int | None = Field(default=None, ge=0, le=MAX_GST_BP)
    is_active: bool | None = None


class MovementActor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    movement_type: MovementType
    on_hand_delta: int
    reserved_delta: int
    quantity_on_hand_after: int
    quantity_reserved_after: int
    reference_type: ReferenceType
    reference_id: int | None = None
    note: str
    created_by: MovementActor | None = None
    created_at: datetime


__all__ = [
    "InventoryEmbed",
    "MovementActor",
    "MovementOut",
    "ProductCreate",
    "ProductLookup",
    "ProductOut",
    "ProductUpdate",
]
