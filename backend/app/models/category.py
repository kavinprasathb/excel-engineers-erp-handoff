from sqlalchemy import Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Category(Base, TimestampMixin):
    """Flat product grouping — "Centrifugal Pumps", "Valves", "Spares".

    Deliberately no hierarchy. Add `parent_id` if the catalogue ever needs it.
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    __table_args__ = (Index("uq_categories_name_lower", func.lower(name), unique=True),)
