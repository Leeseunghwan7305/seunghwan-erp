from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import Account
from ..schemas import AccountIn

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[Account])
def list_accounts(session: Session = Depends(get_session)):
    return session.exec(select(Account).order_by(Account.code)).all()


@router.post("", response_model=Account, status_code=201)
def create_account(payload: AccountIn, session: Session = Depends(get_session)):
    if session.exec(select(Account).where(Account.code == payload.code)).first():
        raise HTTPException(status_code=409, detail="이미 존재하는 계정 코드입니다.")
    acc = Account.model_validate(payload)
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc


@router.put("/{account_id}", response_model=Account)
def update_account(
    account_id: int, payload: AccountIn, session: Session = Depends(get_session)
):
    acc = session.get(Account, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="계정과목을 찾을 수 없습니다.")
    dup = session.exec(select(Account).where(Account.code == payload.code)).first()
    if dup and dup.id != account_id:
        raise HTTPException(status_code=409, detail="이미 존재하는 계정 코드입니다.")
    acc.code = payload.code
    acc.name = payload.name
    acc.category = payload.category
    acc.entry_side = payload.entry_side
    acc.memo = payload.memo
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: int, session: Session = Depends(get_session)):
    acc = session.get(Account, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="계정과목을 찾을 수 없습니다.")
    session.delete(acc)
    session.commit()
