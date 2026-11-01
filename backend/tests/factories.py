"""Small helpers for building test rows.

Deliberately not a factory library: the schema is small, and explicit helpers
read better in assertions than a DSL.
"""

from itertools import count

from sqlalchemy.orm import Session

from app.models import Inventory, Product, Supplier

_seq = count(1)


def make_product(
    db: Session,
    *,
    sku: str | None = None,
    name: str = "Test pump",
    on_hand: int = 0,
    reserved: int = 0,
    supplier: Supplier | None = None,
) -> Product:
    """A product with its inventory row, created the way the app creates them.

    Counters are seeded directly here rather than through the stock service so
    that a test can start from an arbitrary state — including states the
    service itself would refuse to produce — without polluting the ledger.
    """
    n = next(_seq)
    product = Product(
        sku=sku or f"SKU-{n}",
        name=name,
        model_number=f"M-{n}",
        supplier_id=supplier.id if supplier else None,
    )
    db.add(product)
    db.flush()

    inv = Inventory(product_id=product.id, quantity_on_hand=on_hand, quantity_reserved=reserved)
    db.add(inv)
    # The guard blocks UPDATEs to Inventory outside the stock service; a fresh
    # INSERT is not a dirty object, so seeding this way is allowed by design.
    db.flush()
    db.refresh(inv, ["quantity_available"])
    return product


def make_supplier(db: Session, *, name: str | None = None) -> Supplier:
    supplier = Supplier(name=name or f"Supplier {next(_seq)}")
    db.add(supplier)
    db.flush()
    return supplier


def inventory_of(db: Session, product: Product) -> Inventory:
    inv = db.query(Inventory).filter(Inventory.product_id == product.id).one()
    db.refresh(inv, ["quantity_available"])
    return inv
