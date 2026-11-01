"""What was quoted before, for the description box of a quotation line.

Two sources, one list: items read from the client's past offer letters
(`past_offer_items`) and item lines of quotations made in the app. Every
word typed must appear in the description (or, for a past spare part, the
pump model it was listed under), in any order, so "impeller etn" finds an
impeller quoted under "Model: ETN 65-50-160". The customer being quoted comes
first, then the newest; the same description at the same rate is shown once.
Read-only: nothing here writes or moves stock.
"""

from datetime import date
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..constants import LineKind
from ..models import Customer, PastOfferItem, Quotation, QuotationLine
from .like import LIKE_ESCAPE, contains

MAX_SCAN = 40  # rows read from each source before merging


def suggest(
    db: Session, q: str, *, customer_id: int | None = None, limit: int = 8
) -> list[dict[str, Any]]:
    words = [w for w in q.split() if len(w) >= 2][:6]
    if not words:
        return []

    past = db.execute(
        select(PastOfferItem)
        .where(
            # A spare part is listed under its pump ("Model: ETN 65-50-160"):
            # the words may be in the item or in that model heading.
            and_(
                *(
                    or_(
                        PastOfferItem.description.ilike(contains(w), escape=LIKE_ESCAPE),
                        PastOfferItem.details.ilike(contains(w), escape=LIKE_ESCAPE),
                    )
                    for w in words
                )
            )
        )
        .order_by(
            (PastOfferItem.customer_id == customer_id).desc().nulls_last(),
            PastOfferItem.offer_date.desc().nulls_last(),
        )
        .limit(MAX_SCAN)
    ).scalars()
    found: list[dict[str, Any]] = [
        {
            "description": p.description,
            "details": p.details,
            "part_no": p.part_no,
            "moc": p.moc,
            "unit": p.unit,
            "rate_paise": p.rate_paise,
            "hsn_code": p.hsn_code,
            "offer_no": p.offer_no,
            "offer_date": p.offer_date,
            "customer_name": p.customer_name,
            "same_customer": customer_id is not None and p.customer_id == customer_id,
            "source": "past offer",
        }
        for p in past
    ]

    made = db.execute(
        select(
            QuotationLine,
            Quotation.number,
            Quotation.quote_date,
            Quotation.customer_id,
            Customer.name,
        )
        .join(Quotation, Quotation.id == QuotationLine.quotation_id)
        .join(Customer, Customer.id == Quotation.customer_id)
        .where(
            QuotationLine.kind == LineKind.PRODUCT,
            and_(
                *(QuotationLine.description.ilike(contains(w), escape=LIKE_ESCAPE) for w in words)
            ),
        )
        .order_by(Quotation.quote_date.desc(), Quotation.id.desc())
        .limit(MAX_SCAN)
    ).all()
    found += [
        {
            "description": ln.description.split("\n")[0],
            "details": "",
            "part_no": ln.part_no,
            "moc": ln.moc,
            "unit": ln.unit_label,
            "rate_paise": ln.rate_paise,
            "hsn_code": ln.hsn_code,
            "offer_no": number,
            "offer_date": quote_date,
            "customer_name": name,
            "same_customer": customer_id is not None and cust == customer_id,
            "source": "quotation",
        }
        for ln, number, quote_date, cust, name in made
    ]

    found.sort(key=lambda s: (not s["same_customer"], -(s["offer_date"] or date.min).toordinal()))
    seen: set[tuple[str, int]] = set()
    out = []
    for s in found:
        key = (" ".join(s["description"].lower().split()), s["rate_paise"])
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) == limit:
            break
    return out
