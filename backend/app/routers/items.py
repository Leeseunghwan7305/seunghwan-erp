from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import Item, Stock
from ..schemas import ItemCreate, ItemRead, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])


def _to_read(item: Item, qty: int) -> ItemRead:
    return ItemRead(
        id=item.id,
        code=item.code,
        name=item.name,
        unit=item.unit,
        purchase_price=item.purchase_price,
        sale_price=item.sale_price,
        safety_stock=item.safety_stock,
        quantity=qty,
        below_safety=qty < item.safety_stock,
    )


@router.get("", response_model=list[ItemRead])
def list_items(session: Session = Depends(get_session)):
    items = session.exec(select(Item)).all()
    result = []
    for item in items:
        stock = session.exec(select(Stock).where(Stock.item_id == item.id)).first()
        result.append(_to_read(item, stock.quantity if stock else 0))
    return result


@router.post("", response_model=ItemRead, status_code=201)
def create_item(payload: ItemCreate, session: Session = Depends(get_session)):
    exists = session.exec(select(Item).where(Item.code == payload.code)).first()
    if exists:
        raise HTTPException(status_code=409, detail="이미 존재하는 품목 코드입니다.")

    item = Item(
        code=payload.code,
        name=payload.name,
        unit=payload.unit,
        purchase_price=payload.purchase_price,
        sale_price=payload.sale_price,
        safety_stock=payload.safety_stock,
    )
    session.add(item)
    session.commit()
    session.refresh(item)

    stock = Stock(item_id=item.id, quantity=payload.initial_stock)
    session.add(stock)
    session.commit()

    return _to_read(item, stock.quantity)


@router.put("/{item_id}", response_model=ItemRead)
def update_item(item_id: int, payload: ItemUpdate, session: Session = Depends(get_session)):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="품목을 찾을 수 없습니다.")
    item.name = payload.name
    item.unit = payload.unit
    item.purchase_price = payload.purchase_price
    item.sale_price = payload.sale_price
    item.safety_stock = payload.safety_stock
    session.add(item)

    stock = session.exec(select(Stock).where(Stock.item_id == item.id)).first()
    if not stock:
        stock = Stock(item_id=item.id, quantity=0)
    stock.quantity = payload.quantity
    session.add(stock)

    session.commit()
    session.refresh(item)
    return _to_read(item, stock.quantity)


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="품목을 찾을 수 없습니다.")
    for stock in session.exec(select(Stock).where(Stock.item_id == item.id)).all():
        session.delete(stock)
    session.delete(item)
    session.commit()
