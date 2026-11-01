"""Customers, in and out.

The same rule as `supplier.py`: optional *text* is `""` and never `null`. The
one shape difference is the split billing/shipping address — blank shipping
fields mean "same as billing", and nothing here copies one into the other.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from .contacts import clean_emails, clean_phones, merge_contacts
from .party import CUSTOMER_REQUIRED, missing_required


class CustomerRef(BaseModel):
    """The two fields any other row needs to render a customer chip."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CustomerOption(BaseModel):
    """`/customers/options` — the same shape as CustomerRef.

    Kept as its own name so the generated TypeScript reads honestly at the call
    site (a dropdown's options are not "a reference to a customer").
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    contact_person: str
    designation: str
    phone: str
    email: str
    emails: list[str]
    phones: list[str]
    gstin: str
    billing_address_line1: str
    billing_address_line2: str
    billing_city: str
    billing_state: str
    billing_pincode: str
    shipping_address_line1: str
    shipping_address_line2: str
    shipping_city: str
    shipping_state: str
    shipping_pincode: str
    notes: str
    is_active: bool
    branches: list["CustomerBranchOut"]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def missing_fields(self) -> list[str]:
        """Mandatory fields a record saved before they were mandatory still lacks."""
        return missing_required(self, CUSTOMER_REQUIRED)


class CustomerCreate(BaseModel):
    """Bounds mirror the column lengths so an over-long value is a 422, not a 500."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    contact_person: str = Field(default="", max_length=150)
    designation: str = Field(default="", max_length=100)
    phone: str = Field(default="", max_length=30)
    email: str = Field(default="", max_length=255)
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    gstin: str = Field(default="", max_length=20)
    billing_address_line1: str = Field(default="", max_length=255)
    billing_address_line2: str = Field(default="", max_length=255)
    billing_city: str = Field(default="", max_length=100)
    billing_state: str = Field(default="", max_length=100)
    billing_pincode: str = Field(default="", max_length=10)
    shipping_address_line1: str = Field(default="", max_length=255)
    shipping_address_line2: str = Field(default="", max_length=255)
    shipping_city: str = Field(default="", max_length=100)
    shipping_state: str = Field(default="", max_length=100)
    shipping_pincode: str = Field(default="", max_length=10)
    notes: str = Field(default="")
    is_active: bool = True

    @model_validator(mode="before")
    @classmethod
    def _contacts(cls, data: Any) -> Any:
        return merge_contacts(data, partial=False)


class CustomerUpdate(BaseModel):
    """All optional: PATCH changes what was sent and leaves the rest alone."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    contact_person: str | None = Field(default=None, max_length=150)
    designation: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    emails: list[str] | None = None
    phones: list[str] | None = None
    gstin: str | None = Field(default=None, max_length=20)
    billing_address_line1: str | None = Field(default=None, max_length=255)
    billing_address_line2: str | None = Field(default=None, max_length=255)
    billing_city: str | None = Field(default=None, max_length=100)
    billing_state: str | None = Field(default=None, max_length=100)
    billing_pincode: str | None = Field(default=None, max_length=10)
    shipping_address_line1: str | None = Field(default=None, max_length=255)
    shipping_address_line2: str | None = Field(default=None, max_length=255)
    shipping_city: str | None = Field(default=None, max_length=100)
    shipping_state: str | None = Field(default=None, max_length=100)
    shipping_pincode: str | None = Field(default=None, max_length=10)
    notes: str | None = None
    is_active: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _contacts(cls, data: Any) -> Any:
        return merge_contacts(data, partial=True)


class CustomerBranchRef(BaseModel):
    """What a document needs to name the branch it is addressed to."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class CustomerBranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    gstin: str
    contact_person: str
    designation: str
    emails: list[str]
    phones: list[str]
    address_line1: str
    city: str
    state: str
    pincode: str
    is_active: bool


class CustomerBranchCreate(BaseModel):
    """GST number, city, state and pin code are checked by the service."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    gstin: str = Field(default="", max_length=20)
    contact_person: str = Field(default="", max_length=150)
    designation: str = Field(default="", max_length=100)
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


class CustomerBranchUpdate(BaseModel):
    """All optional: PATCH changes what was sent and leaves the rest alone."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    gstin: str | None = Field(default=None, max_length=20)
    contact_person: str | None = Field(default=None, max_length=150)
    designation: str | None = Field(default=None, max_length=100)
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


CustomerOut.model_rebuild()

__all__ = [
    "CustomerBranchCreate",
    "CustomerBranchOut",
    "CustomerBranchRef",
    "CustomerBranchUpdate",
    "CustomerCreate",
    "CustomerOption",
    "CustomerOut",
    "CustomerRef",
    "CustomerUpdate",
]
