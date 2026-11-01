"""Pydantic request/response schemas. Import `Page` from here."""

from .auth import ChangePasswordRequest, LoginRequest, LoginResponse, UserOut
from .category import CategoryCreate, CategoryOut, CategoryRef, CategoryUpdate
from .common import ErrorDetail, ErrorResponse, Page
from .import_job import ImportJobAccepted, ImportJobOut
from .inventory import (
    InventoryRowOut,
    InventorySummaryOut,
    StockAdjustRequest,
    SupplierAssignRequest,
)
from .product import (
    InventoryEmbed,
    MovementActor,
    MovementOut,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)
from .settings import SettingsOut, SettingsUpdate
from .supplier import SupplierCreate, SupplierOption, SupplierOut, SupplierRef, SupplierUpdate

__all__ = [
    "CategoryCreate",
    "CategoryOut",
    "CategoryRef",
    "CategoryUpdate",
    "ChangePasswordRequest",
    "ErrorDetail",
    "ErrorResponse",
    "ImportJobAccepted",
    "ImportJobOut",
    "InventoryEmbed",
    "InventoryRowOut",
    "InventorySummaryOut",
    "LoginRequest",
    "LoginResponse",
    "MovementActor",
    "MovementOut",
    "Page",
    "ProductCreate",
    "ProductOut",
    "ProductUpdate",
    "SettingsOut",
    "SettingsUpdate",
    "StockAdjustRequest",
    "SupplierAssignRequest",
    "SupplierCreate",
    "SupplierOption",
    "SupplierOut",
    "SupplierRef",
    "SupplierUpdate",
    "UserOut",
]
