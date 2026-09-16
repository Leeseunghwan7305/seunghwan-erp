from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import Expense
from ..schemas import ExpenseIn

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("", response_model=list[Expense])
def list_expenses(session: Session = Depends(get_session)):
    return session.exec(
        select(Expense).order_by(Expense.expense_date.desc(), Expense.id.desc())
    ).all()


@router.post("", response_model=Expense, status_code=201)
def create_expense(payload: ExpenseIn, session: Session = Depends(get_session)):
    exp = Expense.model_validate(payload)
    session.add(exp)
    session.commit()
    session.refresh(exp)
    return exp


@router.put("/{expense_id}", response_model=Expense)
def update_expense(
    expense_id: int, payload: ExpenseIn, session: Session = Depends(get_session)
):
    exp = session.get(Expense, expense_id)
    if not exp:
        raise HTTPException(status_code=404, detail="비용 내역을 찾을 수 없습니다.")
    exp.expense_date = payload.expense_date
    exp.account = payload.account
    exp.memo = payload.memo
    exp.dept = payload.dept
    exp.method = payload.method
    exp.amount = payload.amount
    session.add(exp)
    session.commit()
    session.refresh(exp)
    return exp


@router.delete("/{expense_id}", status_code=204)
def delete_expense(expense_id: int, session: Session = Depends(get_session)):
    exp = session.get(Expense, expense_id)
    if not exp:
        raise HTTPException(status_code=404, detail="비용 내역을 찾을 수 없습니다.")
    session.delete(exp)
    session.commit()
