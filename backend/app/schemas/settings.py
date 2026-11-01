"""The settings singleton, in and out.

Theme is absent on purpose: it is per-viewer and lives in the browser's
localStorage, so putting it here would make one person's preference everyone's.

The letterhead lives here because every printed document carries it. Editing
the GST number or the phone number is an admin filling in a form, not a
developer editing a template and redeploying — and the company's 2020 offers
against its 2026 ones prove those details do change.
"""

from pydantic import BaseModel, ConfigDict, Field

from ..constants import QuotationType


class SpecDefault(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=100)
    value: str = Field(default="", max_length=2000)


class TermDefault(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=100)
    text: str = Field(max_length=2000)


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    company_name: str
    low_stock_threshold: int
    default_gst_rate_bp: int

    company_address_line1: str
    company_address_line2: str
    company_city: str
    company_state: str
    company_pincode: str
    company_gstin: str
    company_phone: str
    company_mobile: str
    company_email: str
    signatory_name: str
    signatory_designation: str
    quotation_terms_defaults: dict[QuotationType, list[TermDefault]]
    quotation_spec_defaults: list[SpecDefault]


class SettingsUpdate(BaseModel):
    """Every field optional — PATCH means "change what I sent, leave the rest".

    The bounds mirror the CHECK constraints and the column widths on
    `app_settings`. The database is still the authority; this only turns a 500
    into a 422 with a usable message.
    """

    model_config = ConfigDict(extra="forbid")

    company_name: str | None = Field(default=None, min_length=1, max_length=200)
    low_stock_threshold: int | None = Field(default=None, ge=0)
    default_gst_rate_bp: int | None = Field(default=None, ge=0, le=10000)

    # Blank is meaningful here, unlike the company name: an address line the
    # letterhead should simply not print is sent as "".
    company_address_line1: str | None = Field(default=None, max_length=255)
    company_address_line2: str | None = Field(default=None, max_length=255)
    company_city: str | None = Field(default=None, max_length=100)
    company_state: str | None = Field(default=None, max_length=100)
    company_pincode: str | None = Field(default=None, max_length=10)
    company_gstin: str | None = Field(default=None, max_length=20)
    company_phone: str | None = Field(default=None, max_length=30)
    company_mobile: str | None = Field(default=None, max_length=30)
    company_email: str | None = Field(default=None, max_length=255)
    signatory_name: str | None = Field(default=None, max_length=150)
    signatory_designation: str | None = Field(default=None, max_length=100)
    # Replaced wholesale: the card sends every type's full list.
    quotation_terms_defaults: dict[QuotationType, list[TermDefault]] | None = None
    quotation_spec_defaults: list[SpecDefault] | None = None


__all__ = ["SettingsOut", "SettingsUpdate", "SpecDefault", "TermDefault"]
