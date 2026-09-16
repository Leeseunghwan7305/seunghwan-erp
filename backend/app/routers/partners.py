from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import Partner
from ..schemas import PartnerCreate

router = APIRouter(prefix="/partners", tags=["partners"])


@router.get("", response_model=list[Partner])
def list_partners(session: Session = Depends(get_session)):
    return session.exec(select(Partner)).all()


@router.post("", response_model=Partner, status_code=201)
def create_partner(payload: PartnerCreate, session: Session = Depends(get_session)):
    partner = Partner.model_validate(payload)
    session.add(partner)
    session.commit()
    session.refresh(partner)
    return partner


@router.put("/{partner_id}", response_model=Partner)
def update_partner(
    partner_id: int, payload: PartnerCreate, session: Session = Depends(get_session)
):
    partner = session.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="거래처를 찾을 수 없습니다.")
    partner.name = payload.name
    partner.kind = payload.kind
    partner.phone = payload.phone
    partner.biz_no = payload.biz_no
    session.add(partner)
    session.commit()
    session.refresh(partner)
    return partner


@router.delete("/{partner_id}", status_code=204)
def delete_partner(partner_id: int, session: Session = Depends(get_session)):
    partner = session.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="거래처를 찾을 수 없습니다.")
    session.delete(partner)
    session.commit()
