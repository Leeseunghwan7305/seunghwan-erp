from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import Employee, Role
from ..schemas import EmployeeIn, EmployeeRead

router = APIRouter(prefix="/employees", tags=["employees"])


def _to_read(emp: Employee, session: Session) -> EmployeeRead:
    role = session.get(Role, emp.role_id) if emp.role_id else None
    return EmployeeRead(
        id=emp.id,
        name=emp.name,
        department=emp.department,
        position=emp.position,
        hire_date=emp.hire_date,
        role_id=emp.role_id,
        role_name=role.name if role else None,
    )


@router.get("", response_model=list[EmployeeRead])
def list_employees(session: Session = Depends(get_session)):
    emps = session.exec(select(Employee).order_by(Employee.id)).all()
    return [_to_read(e, session) for e in emps]


@router.post("", response_model=EmployeeRead, status_code=201)
def create_employee(payload: EmployeeIn, session: Session = Depends(get_session)):
    emp = Employee.model_validate(payload)
    session.add(emp)
    session.commit()
    session.refresh(emp)
    return _to_read(emp, session)


@router.put("/{employee_id}", response_model=EmployeeRead)
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
    emp.role_id = payload.role_id
    session.add(emp)
    session.commit()
    session.refresh(emp)
    return _to_read(emp, session)


@router.delete("/{employee_id}", status_code=204)
def delete_employee(employee_id: int, session: Session = Depends(get_session)):
    emp = session.get(Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="직원을 찾을 수 없습니다.")
    session.delete(emp)
    session.commit()
