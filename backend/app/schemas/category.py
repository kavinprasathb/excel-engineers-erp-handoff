"""Categories — a flat list, small enough that the contract leaves it unpaginated."""

from pydantic import BaseModel, ConfigDict, Field


class CategoryRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    product_count: int = 0


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)


class CategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)


__all__ = ["CategoryCreate", "CategoryOut", "CategoryRef", "CategoryUpdate"]
