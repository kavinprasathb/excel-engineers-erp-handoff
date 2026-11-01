"""Orders (from accepted quotations) and the purchase orders they need."""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..constants import OrderStatus, PurchaseOrderStatus
from ..db import get_db
from ..deps import Pagination, get_current_user, get_pagination, owner_only
from ..errors import NotFound
from ..models import AppSettings, User
from ..schemas.common import Page
from ..schemas.order import OrderOut, PurchaseOrderOut, SetSupplier
from ..services import orders as service
from ..services import quotations as quotations_service
from ..services.purchase_order_pdf import render_purchase_order_pdf

router = APIRouter(tags=["orders"])


@router.get("/orders", response_model=Page[OrderOut])
def list_orders(
    q: str | None = Query(default=None, max_length=200),
    status_: OrderStatus | None = Query(default=None, alias="status"),
    page: Pagination = Depends(get_pagination),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Page[OrderOut]:
    rows, total = service.list_orders(db, q=q, status=status_, offset=page.offset, limit=page.limit)
    return Page.build(
        [OrderOut.model_validate(service.order_out(db, o)) for o in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> OrderOut:
    return OrderOut.model_validate(service.order_out(db, service.get_order(db, order_id)))


@router.get("/orders/{order_id}/purchase-orders", response_model=list[PurchaseOrderOut])
def order_purchase_orders(
    order_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[PurchaseOrderOut]:
    service.get_order(db, order_id)
    return [PurchaseOrderOut.model_validate(p) for p in service.purchase_orders_for(db, order_id)]


@router.post("/orders/{order_id}/recheck", response_model=OrderOut)
def recheck_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrderOut:
    order = service.recheck(db, order_id, actor_id=user.id)
    return OrderOut.model_validate(service.order_out(db, order))


@router.post("/orders/{order_id}/deliver", response_model=OrderOut)
def deliver_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrderOut:
    """Product Delivery."""
    order = service.deliver(db, order_id, actor_id=user.id)
    return OrderOut.model_validate(service.order_out(db, order))


@router.get("/quotations/{quotation_id}/order", response_model=OrderOut)
def order_of_quotation(
    quotation_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> OrderOut:
    order = service.order_for_quotation(db, quotation_id)
    if order is None:
        raise NotFound("This quotation has no order.", quotation_id=quotation_id)
    return OrderOut.model_validate(service.order_out(db, service.get_order(db, order.id)))


@router.post("/quotations/{quotation_id}/order", response_model=OrderOut, status_code=201)
def create_order_for_accepted(
    quotation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrderOut:
    """For a quote accepted before orders existed; idempotent."""
    quotation = quotations_service.get_quotation(db, quotation_id)
    if quotation.status.value != "accepted":
        raise NotFound("Only an accepted quotation has an order.", quotation_id=quotation_id)
    order = service.create_from_quotation(db, quotation, actor_id=user.id)
    db.commit()
    return OrderOut.model_validate(service.order_out(db, service.get_order(db, order.id)))


@router.get("/purchase-orders", response_model=Page[PurchaseOrderOut])
def list_purchase_orders(
    q: str | None = Query(default=None, max_length=200),
    status_: PurchaseOrderStatus | None = Query(default=None, alias="status"),
    page: Pagination = Depends(get_pagination),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Page[PurchaseOrderOut]:
    rows, total = service.list_purchase_orders(
        db, q=q, status=status_, offset=page.offset, limit=page.limit
    )
    return Page.build(
        [PurchaseOrderOut.model_validate(p) for p in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/purchase-orders/{po_id}", response_model=PurchaseOrderOut)
def get_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> PurchaseOrderOut:
    return PurchaseOrderOut.model_validate(service.get_purchase_order(db, po_id))


@router.post("/purchase-orders/{po_id}/supplier", response_model=PurchaseOrderOut)
def set_purchase_order_supplier(
    po_id: int,
    body: SetSupplier,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> PurchaseOrderOut:
    return PurchaseOrderOut.model_validate(
        service.set_po_supplier(db, po_id, body.supplier_id, body.branch_id)
    )


@router.post("/purchase-orders/{po_id}/sent", response_model=PurchaseOrderOut)
def mark_purchase_order_sent(
    po_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> PurchaseOrderOut:
    return PurchaseOrderOut.model_validate(service.mark_po_sent(db, po_id))


@router.post("/purchase-orders/{po_id}/received", response_model=PurchaseOrderOut)
def mark_purchase_order_received(
    po_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PurchaseOrderOut:
    """The goods are in: stock goes up, and waiting orders take what they need."""
    return PurchaseOrderOut.model_validate(service.receive_po(db, po_id, actor_id=user.id))


@router.get("/purchase-orders/{po_id}/pdf", dependencies=[Depends(owner_only)])
def purchase_order_pdf(
    po_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Response:
    po = service.get_purchase_order(db, po_id)
    settings = db.get(AppSettings, 1)
    if settings is None:
        raise NotFound("Application settings row is missing; the database needs repair.")
    return Response(
        content=render_purchase_order_pdf(po, settings),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{po.number}.pdf"'},
    )
