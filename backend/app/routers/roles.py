from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import Employee, Role
from ..schemas import RoleIn

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=list[Role])
def list_roles(session: Session = Depends(get_session)):
    return session.exec(select(Role).order_by(Role.id)).all()


@router.post("", response_model=Role, status_code=201)
def create_role(payload: RoleIn, session: Session = Depends(get_session)):
    if session.exec(select(Role).where(Role.name == payload.name)).first():
        raise HTTPException(status_code=409, detail="이미 존재하는 역할명입니다.")
    role = Role.model_validate(payload)
    session.add(role)
    session.commit()
    session.refresh(role)
    return role


@router.put("/{role_id}", response_model=Role)
def update_role(role_id: int, payload: RoleIn, session: Session = Depends(get_session)):
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="역할을 찾을 수 없습니다.")
    dup = session.exec(select(Role).where(Role.name == payload.name)).first()
    if dup and dup.id != role_id:
        raise HTTPException(status_code=409, detail="이미 존재하는 역할명입니다.")
    role.name = payload.name
    role.description = payload.description
    role.permissions = payload.permissions
    session.add(role)
    session.commit()
    session.refresh(role)
    return role


@router.delete("/{role_id}", status_code=204)
def delete_role(role_id: int, session: Session = Depends(get_session)):
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="역할을 찾을 수 없습니다.")
    # 이 역할을 쓰는 직원의 role_id를 해제
    for emp in session.exec(select(Employee).where(Employee.role_id == role_id)).all():
        emp.role_id = None
        session.add(emp)
    session.delete(role)
    session.commit()
