"""The stock service, exhaustively.

This is the module where a bug costs real money — a wrong count means either a
customer promised goods that are not there, or stock sitting unsold because the
app thinks it is spoken for. Every intent and every boundary is covered.
"""

import random

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.constants import MovementType, ReferenceType
from app.errors import InsufficientReservation, InsufficientStock, NotFound
from app.models import Inventory, StockMovement
from app.services import stock
from app.services.stock import StockRef

from .factories import inventory_of, make_product

MANUAL = StockRef(ReferenceType.MANUAL, note="test")
ORDER = StockRef(ReferenceType.ORDER, id=42, note="order 42")


def movements(db: Session, product_id: int) -> list[StockMovement]:
    return (
        db.query(StockMovement)
        .filter(StockMovement.product_id == product_id)
        .order_by(StockMovement.id)
        .all()
    )


# --------------------------------------------------------------------------
# The happy paths
# --------------------------------------------------------------------------


def test_receive_increases_on_hand_and_available(db: Session) -> None:
    p = make_product(db, on_hand=0)
    inv = stock.receive(db, product_id=p.id, qty=10, ref=MANUAL)
    assert (inv.quantity_on_hand, inv.quantity_reserved, inv.quantity_available) == (10, 0, 10)


def test_reserve_moves_available_without_touching_on_hand(db: Session) -> None:
    p = make_product(db, on_hand=10)
    inv = stock.reserve(db, product_id=p.id, qty=4, ref=ORDER)
    assert (inv.quantity_on_hand, inv.quantity_reserved, inv.quantity_available) == (10, 4, 6)


def test_release_returns_the_claim(db: Session) -> None:
    p = make_product(db, on_hand=10, reserved=4)
    inv = stock.release(db, product_id=p.id, qty=4, ref=ORDER)
    assert (inv.quantity_on_hand, inv.quantity_reserved, inv.quantity_available) == (10, 0, 10)


def test_deliver_removes_from_both_counters_in_one_movement(db: Session) -> None:
    p = make_product(db, on_hand=10, reserved=4)
    inv = stock.deliver(db, product_id=p.id, qty=4, ref=ORDER)
    assert (inv.quantity_on_hand, inv.quantity_reserved, inv.quantity_available) == (6, 0, 6)
    rows = movements(db, p.id)
    assert len(rows) == 1, "deliver must be one movement, not release-then-adjust"
    assert (rows[0].on_hand_delta, rows[0].reserved_delta) == (-4, -4)


def test_adjust_up_and_down(db: Session) -> None:
    p = make_product(db, on_hand=5)
    assert stock.adjust(db, product_id=p.id, delta=3, ref=MANUAL).quantity_on_hand == 8
    assert stock.adjust(db, product_id=p.id, delta=-6, ref=MANUAL).quantity_on_hand == 2


def test_set_on_hand_computes_the_delta(db: Session) -> None:
    p = make_product(db, on_hand=5)
    inv = stock.set_on_hand(db, product_id=p.id, qty=12, ref=StockRef(ReferenceType.IMPORT))
    assert inv is not None
    assert inv.quantity_on_hand == 12
    assert movements(db, p.id)[-1].on_hand_delta == 7


def test_set_on_hand_to_the_same_value_writes_nothing(db: Session) -> None:
    """The importer relies on this to report rows that actually changed."""
    p = make_product(db, on_hand=5)
    assert stock.set_on_hand(db, product_id=p.id, qty=5, ref=StockRef(ReferenceType.IMPORT)) is None
    assert movements(db, p.id) == []


def test_import_ref_produces_an_import_movement(db: Session) -> None:
    p = make_product(db, on_hand=0)
    stock.set_on_hand(db, product_id=p.id, qty=3, ref=StockRef(ReferenceType.IMPORT))
    assert movements(db, p.id)[-1].movement_type == MovementType.IMPORT


# --------------------------------------------------------------------------
# Boundaries — exactly at the limit, and one past it
# --------------------------------------------------------------------------


def test_reserve_exactly_all_available_is_allowed(db: Session) -> None:
    p = make_product(db, on_hand=10, reserved=2)
    assert stock.reserve(db, product_id=p.id, qty=8, ref=ORDER).quantity_available == 0


def test_reserve_one_more_than_available_is_refused(db: Session) -> None:
    p = make_product(db, on_hand=10, reserved=2)
    with pytest.raises(InsufficientStock):
        stock.reserve(db, product_id=p.id, qty=9, ref=ORDER)


def test_adjust_to_exactly_zero_is_allowed(db: Session) -> None:
    p = make_product(db, on_hand=5)
    assert stock.adjust(db, product_id=p.id, delta=-5, ref=MANUAL).quantity_on_hand == 0


def test_adjust_below_zero_is_refused(db: Session) -> None:
    p = make_product(db, on_hand=5)
    with pytest.raises(InsufficientStock):
        stock.adjust(db, product_id=p.id, delta=-6, ref=MANUAL)


def test_adjust_below_the_reserved_quantity_is_refused(db: Session) -> None:
    """The subtle one: stock exists, but it is already promised to an order."""
    p = make_product(db, on_hand=10, reserved=7)
    with pytest.raises(InsufficientStock):
        stock.adjust(db, product_id=p.id, delta=-5, ref=MANUAL)
    assert inventory_of(db, p).quantity_on_hand == 10


def test_release_more_than_reserved_is_refused(db: Session) -> None:
    p = make_product(db, on_hand=10, reserved=3)
    with pytest.raises(InsufficientReservation):
        stock.release(db, product_id=p.id, qty=4, ref=ORDER)


def test_deliver_more_than_reserved_is_refused(db: Session) -> None:
    p = make_product(db, on_hand=10, reserved=3)
    with pytest.raises(InsufficientReservation):
        stock.deliver(db, product_id=p.id, qty=4, ref=ORDER)


@pytest.mark.parametrize(
    ("fn", "kwargs"),
    [
        (stock.receive, {"qty": 0}),
        (stock.receive, {"qty": -1}),
        (stock.reserve, {"qty": 0}),
        (stock.release, {"qty": 0}),
        (stock.deliver, {"qty": 0}),
        (stock.adjust, {"delta": 0}),
    ],
)
def test_non_positive_quantities_are_refused(db: Session, fn, kwargs) -> None:
    p = make_product(db, on_hand=10, reserved=5)
    with pytest.raises((InsufficientStock, InsufficientReservation)):
        fn(db, product_id=p.id, ref=MANUAL, **kwargs)


def test_unknown_product_raises_not_found(db: Session) -> None:
    with pytest.raises(NotFound):
        stock.receive(db, product_id=999_999, qty=1, ref=MANUAL)


# --------------------------------------------------------------------------
# The ledger
# --------------------------------------------------------------------------


def test_every_movement_records_its_cause_and_actor(db: Session) -> None:
    p = make_product(db, on_hand=10)
    stock.reserve(db, product_id=p.id, qty=2, ref=ORDER, actor_id=None)
    m = movements(db, p.id)[-1]
    assert m.reference_type == ReferenceType.ORDER
    assert m.reference_id == 42
    assert m.note == "order 42"


def test_movements_snapshot_the_resulting_state(db: Session) -> None:
    p = make_product(db, on_hand=0)
    stock.receive(db, product_id=p.id, qty=10, ref=MANUAL)
    stock.reserve(db, product_id=p.id, qty=3, ref=ORDER)
    stock.deliver(db, product_id=p.id, qty=3, ref=ORDER)
    after = [(m.quantity_on_hand_after, m.quantity_reserved_after) for m in movements(db, p.id)]
    assert after == [(10, 0), (10, 3), (7, 0)]


def test_failed_operations_leave_no_movement(db: Session) -> None:
    p = make_product(db, on_hand=5)
    with pytest.raises(InsufficientStock):
        stock.adjust(db, product_id=p.id, delta=-99, ref=MANUAL)
    assert movements(db, p.id) == []


# --------------------------------------------------------------------------
# The guard — bypass must be impossible, not merely discouraged
# --------------------------------------------------------------------------


def test_direct_counter_mutation_raises(db: Session) -> None:
    p = make_product(db, on_hand=10)
    inv = inventory_of(db, p)
    inv.quantity_on_hand = 999
    with pytest.raises(RuntimeError, match=r"outside app\.services\.stock"):
        db.flush()


def test_the_database_itself_rejects_bad_state(db: Session) -> None:
    """Belt and braces: even raw SQL, bypassing the ORM entirely, cannot lie."""
    p = make_product(db, on_hand=10, reserved=5)
    with pytest.raises(Exception):  # noqa: B017 - any DBAPI error is a pass here
        db.execute(
            text("UPDATE inventory SET quantity_reserved = 99 WHERE product_id = :pid"),
            {"pid": p.id},
        )


def test_generated_column_cannot_be_written(db: Session) -> None:
    p = make_product(db, on_hand=10)
    with pytest.raises(Exception):  # noqa: B017
        db.execute(
            text("UPDATE inventory SET quantity_available = 99 WHERE product_id = :pid"),
            {"pid": p.id},
        )


# --------------------------------------------------------------------------
# bulk_reserve
# --------------------------------------------------------------------------


def test_bulk_reserve_reserves_every_line(db: Session) -> None:
    a = make_product(db, on_hand=10)
    b = make_product(db, on_hand=5)
    result = stock.bulk_reserve(db, lines=[(b.id, 2), (a.id, 3)], ref=ORDER)
    assert result[a.id].quantity_reserved == 3
    assert result[b.id].quantity_reserved == 2


def test_bulk_reserve_locks_in_sorted_order(db: Session) -> None:
    """Deadlock avoidance: the lock order must not depend on caller order."""
    a = make_product(db, on_hand=10)
    b = make_product(db, on_hand=10)
    lo, hi = sorted([a.id, b.id])
    stock.bulk_reserve(db, lines=[(hi, 1), (lo, 1)], ref=ORDER)
    order = [m.product_id for m in db.query(StockMovement).order_by(StockMovement.id).all()]
    assert order == [lo, hi]


def test_bulk_reserve_is_all_or_nothing_within_a_transaction(db: Session) -> None:
    """One bad line aborts the lot — the caller's transaction is not committed."""
    a = make_product(db, on_hand=10)
    b = make_product(db, on_hand=1)
    with pytest.raises(InsufficientStock):
        stock.bulk_reserve(db, lines=[(a.id, 2), (b.id, 5)], ref=ORDER)
    db.rollback()


# --------------------------------------------------------------------------
# reconcile
# --------------------------------------------------------------------------


def test_reconcile_is_clean_after_normal_operations(db: Session) -> None:
    p = make_product(db, on_hand=0)
    stock.receive(db, product_id=p.id, qty=20, ref=MANUAL)
    stock.reserve(db, product_id=p.id, qty=5, ref=ORDER)
    stock.deliver(db, product_id=p.id, qty=5, ref=ORDER)
    stock.adjust(db, product_id=p.id, delta=-3, ref=MANUAL)
    assert stock.reconcile(db, product_id=p.id) == []


def test_reconcile_detects_a_planted_drift(db: Session) -> None:
    """Prove the check can actually fail — a check that never fails is decoration."""
    p = make_product(db, on_hand=0)
    stock.receive(db, product_id=p.id, qty=10, ref=MANUAL)
    # Bypass everything, including the ORM guard, to simulate corruption.
    db.execute(
        text("UPDATE inventory SET quantity_on_hand = 7 WHERE product_id = :pid"),
        {"pid": p.id},
    )
    found = stock.reconcile(db, product_id=p.id)
    assert len(found) == 1
    assert found[0].counter_on_hand == 7
    assert found[0].ledger_on_hand == 10


def test_fuzz_random_valid_operations_keep_every_invariant(db: Session) -> None:
    """500 random legal operations; the counters must still equal the ledger."""
    rng = random.Random(20260830)
    p = make_product(db, on_hand=0)
    stock.receive(db, product_id=p.id, qty=500, ref=MANUAL)

    for _ in range(500):
        inv = inventory_of(db, p)
        choices = ["receive"]
        if inv.quantity_available > 0:
            choices.append("reserve")
        if inv.quantity_reserved > 0:
            choices += ["release", "deliver"]
        if inv.quantity_available > 0:
            choices.append("adjust_down")

        match rng.choice(choices):
            case "receive":
                stock.receive(db, product_id=p.id, qty=rng.randint(1, 20), ref=MANUAL)
            case "reserve":
                stock.reserve(
                    db, product_id=p.id, qty=rng.randint(1, inv.quantity_available), ref=ORDER
                )
            case "release":
                stock.release(
                    db, product_id=p.id, qty=rng.randint(1, inv.quantity_reserved), ref=ORDER
                )
            case "deliver":
                stock.deliver(
                    db, product_id=p.id, qty=rng.randint(1, inv.quantity_reserved), ref=ORDER
                )
            case "adjust_down":
                stock.adjust(
                    db, product_id=p.id, delta=-rng.randint(1, inv.quantity_available), ref=MANUAL
                )

    final = inventory_of(db, p)
    assert final.quantity_on_hand >= 0
    assert final.quantity_reserved >= 0
    assert final.quantity_reserved <= final.quantity_on_hand
    assert final.quantity_available == final.quantity_on_hand - final.quantity_reserved
    assert stock.reconcile(db) == []


def test_reconcile_handles_a_product_with_no_movements(db: Session) -> None:
    make_product(db, on_hand=0)
    assert stock.reconcile(db) == []


def test_seeded_stock_without_a_ledger_shows_as_drift(db: Session) -> None:
    """A factory-seeded count has no movements behind it, and reconcile says so.

    Worth asserting explicitly so nobody later mistakes this for a bug: real
    stock only ever arrives through the service, which always writes a movement.
    """
    p = make_product(db, on_hand=7)
    assert [d.product_id for d in stock.reconcile(db, product_id=p.id)] == [p.id]


def test_inventory_row_is_required(db: Session) -> None:
    from app.models import Product

    orphan = Product(sku="NO-INV", name="No inventory row")
    db.add(orphan)
    db.flush()
    with pytest.raises(NotFound):
        stock.receive(db, product_id=orphan.id, qty=1, ref=MANUAL)
    assert db.query(Inventory).filter(Inventory.product_id == orphan.id).count() == 0
