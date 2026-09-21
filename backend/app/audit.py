"""AI 행동 감사 로그 기록기.

도구 호출·외부 전송(슬랙 등)이 '누가·무엇을·성공여부'로 남도록 한다.
감사 로깅 실패가 기능 자체를 막지 않도록 예외는 삼킨다.
"""
from typing import Optional

from sqlmodel import Session, select

from .database import engine
from .models import AuditLog


def record(action: str, detail: str = "", ok: bool = True, actor: Optional[str] = None) -> None:
    try:
        with Session(engine) as s:
            s.add(AuditLog(action=action, detail=(detail or "")[:500] or None, ok=ok, actor=actor))
            s.commit()
    except Exception:  # noqa: BLE001 - 감사 실패가 대화를 막지 않도록
        pass


def recent(limit: int = 50) -> list[AuditLog]:
    with Session(engine) as s:
        return list(s.exec(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).all())
