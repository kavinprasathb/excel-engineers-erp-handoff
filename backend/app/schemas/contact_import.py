"""Shapes for previewing and committing a customer/supplier import."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .customer import CustomerCreate
from .supplier import SupplierCreate


class DuplicateRef(BaseModel):
    id: int
    name: str


class ImportPreviewRecord(BaseModel):
    # The create-payload shape for the kind being imported. Not validated:
    # the point of the preview is to let the operator fix what is wrong.
    data: dict[str, Any]
    warnings: list[str]
    duplicate_of: DuplicateRef | None = None


class ImportPreview(BaseModel):
    records: list[ImportPreviewRecord]
    # More than 2,000 records were found; only the first 2,000 are returned.
    truncated: bool = False


class CustomerImportCommit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[CustomerCreate] = Field(min_length=1, max_length=2000)


class SupplierImportCommit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[SupplierCreate] = Field(min_length=1, max_length=2000)


class ImportCommitResult(BaseModel):
    created: int
