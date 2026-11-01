"""Suppliers, in and out.

Optional *text* is `""` and never `null` — the contract's rule, enforced here so
the frontend never has to write `supplier.phone ?? ""` at every render site.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from .contacts import clean_emails, clean_phones, merge_contacts
from .party import PARTY_REQUIRED, missing_required


class SupplierRef(BaseModel):
    """The two fields any other row needs to render a supplier chip."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class SupplierOption(BaseModel):
    """`/suppliers/options` — deliberately the same shape as SupplierRef.

    Kept as its own name so the generated TypeScript reads honestly at the call
    site (a dropdown's options are not "a reference to a supplier").
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    contact_person: str
    phone: str
    email: str
    emails: list[str]
    phones: list[str]
    gstin: str
    address_line1: str
    address_line2: str
    city: str
    state: str
    pincode: str
    notes: str
    is_active: bool
    # Computed by the service in the same query as the row; never a lazy count.
    product_count: int = 0
    branches: list["SupplierBranchOut"]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def missing_fields(self) -> list[str]:
        """Mandatory fields a record saved before they were mandatory still lacks."""
        return missing_required(self, PARTY_REQUIRED)


class SupplierCreate(BaseModel):
    """Bounds mirror the column lengths so an over-long value is a 422, not a 500."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    contact_person: str = Field(default="", max_length=150)
    phone: str = Field(default="", max_length=30)
    email: str = Field(default="", max_length=255)
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    gstin: str = Field(default="", max_length=20)
    address_line1: str = Field(default="", max_length=255)
    address_line2: str = Field(default="", max_length=255)
    city: str = Field(default="", max_length=100)
    state: str = Field(default="", max_length=100)
    pincode: str = Field(default="", max_length=10)
    notes: str = Field(default="")
    is_active: bool = True

    @model_validator(mode="before")
    @classmethod
    def _contacts(cls, data: Any) -> Any:
        return merge_contacts(data, partial=False)


class SupplierUpdate(BaseModel):
    """All optional: PATCH changes what was sent and leaves the rest alone."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    contact_person: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    emails: list[str] | None = None
    phones: list[str] | None = None
    gstin: str | None = Field(default=None, max_length=20)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=10)
    notes: str | None = None
    is_active: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _contacts(cls, data: Any) -> Any:
        return merge_contacts(data, partial=True)


class SupplierBranchRef(BaseModel):
    """What a document needs to name the branch it is addressed to."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class SupplierBranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    gstin: str
    emails: list[str]
    phones: list[str]
    address_line1: str
    city: str
    state: str
    pincode: str
    is_active: bool


class SupplierBranchCreate(BaseModel):
    """GST number, city, state and pin code are checked by the service."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    gstin: str = Field(default="", max_length=20)
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    address_line1: str = Field(default="", max_length=255)
    city: str = Field(default="", max_length=100)
    state: str = Field(default="", max_length=100)
    pincode: str = Field(default="", max_length=10)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Enter the branch name.")
        return v.strip()

    @field_validator("emails")
    @classmethod
    def _emails(cls, v: list[str]) -> list[str]:
        return clean_emails(v)

    @field_validator("phones")
    @classmethod
    def _phones(cls, v: list[str]) -> list[str]:
        return clean_phones(v)


class SupplierBranchUpdate(BaseModel):
    """All optional: PATCH changes what was sent and leaves the rest alone."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    gstin: str | None = Field(default=None, max_length=20)
    emails: list[str] | None = None
    phones: list[str] | None = None
    address_line1: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=10)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Enter the branch name.")
        return None if v is None else v.strip()

    @field_validator("emails")
    @classmethod
    def _emails(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else clean_emails(v)

    @field_validator("phones")
    @classmethod
    def _phones(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else clean_phones(v)


SupplierOut.model_rebuild()

__all__ = [
    "SupplierBranchCreate",
    "SupplierBranchOut",
    "SupplierBranchRef",
    "SupplierBranchUpdate",
    "SupplierCreate",
    "SupplierOption",
    "SupplierOut",
    "SupplierRef",
    "SupplierUpdate",
]
