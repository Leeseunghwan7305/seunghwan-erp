from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import (
    Item,
    Order,
    OrderLine,
    OrderStatus,
    OrderType,
    Partner,
    PaymentStatus,
    Stock,
    Voucher,
    VoucherType,
)
from ..schemas import OrderCreate, OrderLineRead, OrderRead

router = APIRouter(prefix="/orders", tags=["orders"])


def _to_read(order: Order, session: Session) -> OrderRead:
    partner = session.get(Partner, order.partner_id)
    lines = []
    for line in order.lines:
        item = session.get(Item, line.item_id)
        lines.append(
            OrderLineRead(
                item_id=line.item_id,
                item_name=item.name if item else "(삭제됨)",
                quantity=line.quantity,
                unit_price=line.unit_price,
                amount=line.amount,
            )
        )
    return OrderRead(
        id=order.id,
        order_type=order.order_type,
        partner_id=order.partner_id,
        partner_name=partner.name if partner else "(삭제됨)",
        order_date=order.order_date.isoformat(),
        status=order.status.value,
        total=order.total,
        lines=lines,
    )


@router.get("", response_model=list[OrderRead])
def list_orders(session: Session = Depends(get_session)):
    orders = session.exec(select(Order).order_by(Order.id.desc())).all()
    return [_to_read(o, session) for o in orders]


@router.get("/{order_id}", response_model=OrderRead)
def get_order(order_id: int, session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    return _to_read(order, session)


@router.post("", response_model=OrderRead, status_code=201)
def create_order(payload: OrderCreate, session: Session = Depends(get_session)):
    if not payload.lines:
        raise HTTPException(status_code=400, detail="주문 항목이 최소 1개 필요합니다.")

    partner = session.get(Partner, payload.partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="거래처를 찾을 수 없습니다.")

    order = Order(order_type=payload.order_type, partner_id=payload.partner_id)
    session.add(order)
    session.flush()  # order.id 확보

    total = 0
    for line_in in payload.lines:
        item = session.get(Item, line_in.item_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"품목 {line_in.item_id} 없음")
        # 단가 미지정 시 주문 유형에 따라 기본가 적용
        if line_in.unit_price is not None:
            unit_price = line_in.unit_price
        elif payload.order_type == OrderType.purchase:
            unit_price = item.purchase_price
        else:
            unit_price = item.sale_price
        amount = unit_price * line_in.quantity
        total += amount
        session.add(
            OrderLine(
                order_id=order.id,
                item_id=item.id,
                quantity=line_in.quantity,
                unit_price=unit_price,
                amount=amount,
            )
        )

    order.total = total
    session.add(order)
    session.commit()
    session.refresh(order)
    return _to_read(order, session)


@router.delete("/{order_id}", status_code=204)
def delete_order(order_id: int, session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    if order.status != OrderStatus.draft:
        raise HTTPException(
            status_code=409,
            detail="확정된 주문은 삭제할 수 없습니다(재고·전표 반영됨).",
        )
    session.delete(order)  # OrderLine은 cascade 삭제
    session.commit()


@router.post("/{order_id}/confirm", response_model=OrderRead)
def confirm_order(order_id: int, session: Session = Depends(get_session)):
    """주문 확정 — 재고를 자동 반영하고 전표를 생성한다. (프로토타입 핵심 로직)"""
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    if order.status != OrderStatus.draft:
        raise HTTPException(status_code=409, detail="이미 확정된 주문입니다.")

    # 판매 주문은 재고가 충분한지 먼저 검증
    if order.order_type == OrderType.sale:
        for line in order.lines:
            stock = session.exec(select(Stock).where(Stock.item_id == line.item_id)).first()
            available = stock.quantity if stock else 0
            if available < line.quantity:
                item = session.get(Item, line.item_id)
                raise HTTPException(
                    status_code=409,
                    detail=f"재고 부족: {item.name if item else line.item_id} (현재 {available}, 요청 {line.quantity})",
                )

    # 재고 반영: 구매=입고(+), 판매=출고(-)
    sign = 1 if order.order_type == OrderType.purchase else -1
    for line in order.lines:
        stock = session.exec(select(Stock).where(Stock.item_id == line.item_id)).first()
        if not stock:
            stock = Stock(item_id=line.item_id, quantity=0)
        stock.quantity += sign * line.quantity
        session.add(stock)

    # 전표 생성 (매입/매출)
    voucher = Voucher(
        voucher_type=(
            VoucherType.purchase if order.order_type == OrderType.purchase else VoucherType.sale
        ),
        order_id=order.id,
        partner_id=order.partner_id,
        amount=order.total,
        payment_status=PaymentStatus.unpaid,
    )
    session.add(voucher)

    order.status = OrderStatus.confirmed
    session.add(order)
    session.commit()
    session.refresh(order)
    return _to_read(order, session)
