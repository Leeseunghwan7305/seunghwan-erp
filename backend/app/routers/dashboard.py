from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..database import get_session
from ..models import (
    Item,
    Order,
    OrderStatus,
    Partner,
    PaymentStatus,
    Stock,
    Voucher,
    VoucherType,
)
from ..schemas import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardSummary)
def summary(session: Session = Depends(get_session)):
    items = session.exec(select(Item)).all()
    stocks = {s.item_id: s.quantity for s in session.exec(select(Stock)).all()}
    partners = session.exec(select(Partner)).all()
    orders = session.exec(select(Order)).all()
    vouchers = session.exec(select(Voucher)).all()

    below_safety = sum(
        1 for it in items if stocks.get(it.id, 0) < it.safety_stock
    )

    sales_total = sum(v.amount for v in vouchers if v.voucher_type == VoucherType.sale)
    purchase_total = sum(
        v.amount for v in vouchers if v.voucher_type == VoucherType.purchase
    )
    receivable = sum(
        v.amount
        for v in vouchers
        if v.voucher_type == VoucherType.sale and v.payment_status == PaymentStatus.unpaid
    )
    payable = sum(
        v.amount
        for v in vouchers
        if v.voucher_type == VoucherType.purchase and v.payment_status == PaymentStatus.unpaid
    )
    open_orders = sum(1 for o in orders if o.status != OrderStatus.done)

    return DashboardSummary(
        item_count=len(items),
        partner_count=len(partners),
        total_stock_qty=sum(stocks.values()),
        below_safety_count=below_safety,
        sales_total=sales_total,
        purchase_total=purchase_total,
        receivable=receivable,
        payable=payable,
        open_orders=open_orders,
    )
