from typing import Any, Optional

from fastapi import APIRouter
from sqlmodel import SQLModel

from .planner import apply_proposal, plan

router = APIRouter(prefix="/agent", tags=["agent"])


class PlanRequest(SQLModel):
    instruction: str
    screen: Optional[str] = None


class ApplyRequest(SQLModel):
    proposal: dict[str, Any]


@router.post("/plan")
def agent_plan(req: PlanRequest):
    """자연어 명령 → 구조화 제안(미리보기). DB 변경 없음."""
    return plan(req.screen or "", req.instruction)


@router.post("/apply")
def agent_apply(req: ApplyRequest):
    """사용자가 확인한 제안을 실제로 실행한다."""
    p = req.proposal or {}
    if not p.get("ok"):
        return {"ok": False, "error": "유효하지 않은 제안입니다."}
    return apply_proposal(p)
