from sqlalchemy import CheckConstraint, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class AppSettings(Base, TimestampMixin):
    """Company-wide settings. Exactly one row, id 1.

    CHECK (id = 1) makes the singleton a schema guarantee, and the migration
    inserts the row, so no code needs a get-or-create path.

    The letterhead block exists because every printed document carries it. Holding
    it here rather than in the template means the GST number and the phone
    number are changed by the admin in Settings, not by a developer in a
    deploy - and the 2020 offer proves they do change.
    """

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True, server_default=text("1"))
    company_name: Mapped[str] = mapped_column(
        String(200), nullable=False, server_default="Excel Engineers"
    )
    low_stock_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("5")
    )
    default_gst_rate_bp: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1800")
    )

    # --- Letterhead, printed at the head and foot of every document ---
    company_address_line1: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default="G2, VKP Residency, 146, Dhayanandhar Street"
    )
    company_address_line2: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default="New Fairlands"
    )
    company_city: Mapped[str] = mapped_column(String(100), nullable=False, server_default="Salem")
    company_state: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="Tamil Nadu"
    )
    company_pincode: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="636016"
    )
    company_gstin: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="33AAIFE2328P1Z9"
    )
    company_phone: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="0427 244 0808"
    )
    company_mobile: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="94449 15716"
    )
    company_email: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default="excelengrs@gmail.com"
    )
    signatory_name: Mapped[str] = mapped_column(
        String(150), nullable=False, server_default="M. Rajamuthaiyah"
    )
    signatory_designation: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default=""
    )

    # Per quotation type, the ordered [{label, text}] a new quote starts with.
    # JSONB: the admin edits the whole list at once and nothing queries inside
    # it. Seeded by the migration, so a blank {} means "someone wiped it".
    quotation_terms_defaults: Mapped[dict[str, list[dict[str, str]]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    # The technical deviation rows every new item line starts with: [{label, value}].
    quotation_spec_defaults: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint("low_stock_threshold >= 0", name="low_stock_threshold_non_negative"),
        CheckConstraint(
            "default_gst_rate_bp BETWEEN 0 AND 10000", name="default_gst_rate_bp_range"
        ),
    )
