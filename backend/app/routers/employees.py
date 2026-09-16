from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import Employee
from ..schemas import EmployeeIn

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("", response_model=list[Employee])
def list_employees(session: Session = Depends(get_session)):
    return session.exec(select(Employee).order_by(Employee.id)).all()


@router.post("", response_model=Employee, status_code=201)
def create_employee(payload: EmployeeIn, session: Session = Depends(get_session)):
    emp = Employee.model_validate(payload)
    session.add(emp)
    session.commit()
    session.refresh(emp)
    return emp


@router.put("/{employee_id}", response_model=Employee)
def update_employee(
    employee_id: int, payload: EmployeeIn, session: Session = Depends(get_session)
):
    emp = session.get(Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="직원을 찾을 수 없습니다.")
    emp.name = payload.name
    emp.department = payload.department
    emp.position = payload.position
    emp.hire_date = payload.hire_date
    session.add(emp)
    session.commit()
    session.refresh(emp)
    return emp


@router.delete("/{employee_id}", status_code=204)
def delete_employee(employee_id: int, session: Session = Depends(get_session)):
    emp = session.get(Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="직원을 찾을 수 없습니다.")
    session.delete(emp)
    session.commit()
