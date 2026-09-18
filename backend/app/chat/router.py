import json
from typing import Literal, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlmodel import SQLModel

from .providers import run_chat

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(SQLModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(SQLModel):
    model: Literal["claude", "local"] = "claude"
    messages: list[ChatMessage]
    # 문서 자동검색 임계값 override. 도움말 도우미가 0.35 정도로 낮춰 SOP를 더 잘 찾게 함.
    doc_min_score: Optional[float] = None


@router.post("")
def chat(req: ChatRequest):
    """모델(Claude/로컬)에게 대화를 보내고 도구 호출·최종 답변을 SSE로 스트리밍."""

    def event_stream():
        msgs = [{"role": m.role, "content": m.content} for m in req.messages]
        for event in run_chat(req.model, msgs, doc_min_score=req.doc_min_score):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
