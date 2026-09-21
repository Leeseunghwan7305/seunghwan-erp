from typing import Optional

from fastapi import APIRouter
from sqlmodel import SQLModel

from ..audit import recent
from .slack import send_message

router = APIRouter(prefix="/integrations", tags=["integrations"])


class SlackSend(SQLModel):
    message: str
    actor: Optional[str] = None


@router.post("/slack/send")
def slack_send(req: SlackSend):
    """사용자 확인 후에만 호출되는 슬랙 전송 엔드포인트."""
    return send_message(req.message, req.actor)


@router.get("/audit")
def audit_log(limit: int = 50):
    """감사 로그(최근순) — 누가·무슨 도구/전송을·성공여부."""
    return [
        {
            "ts": a.ts.isoformat(),
            "actor": a.actor,
            "action": a.action,
            "detail": a.detail,
            "ok": a.ok,
        }
        for a in recent(limit)
    ]
