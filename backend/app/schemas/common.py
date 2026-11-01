"""Shapes shared by every endpoint.

`Page` is generic so that FastAPI emits a distinct OpenAPI schema per item type
(`PageProduct`, `PageSupplier`, …) and the generated TypeScript keeps its
element type. A `list[Any]` here would erase that on the frontend, which is the
whole reason the contract is generated rather than hand-written.
"""

from collections.abc import Sequence
from math import ceil

from pydantic import BaseModel, Field


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(cls, items: Sequence[T], *, total: int, page: int, page_size: int) -> "Page[T]":
        """`pages` is derived here, never passed in.

        Two callers computing it is two chances for them to disagree.
        """
        return cls(
            items=list(items),
            total=total,
            page=page,
            page_size=page_size,
            pages=ceil(total / page_size) if page_size else 0,
        )


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """The envelope every failure uses. Never a bare string, never a traceback."""

    error: ErrorDetail


__all__ = ["ErrorDetail", "ErrorResponse", "Page"]
