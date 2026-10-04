import json
from typing import Any, Literal, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlmodel import SQLModel

from .planner import apply_proposal, plan

router = APIRouter(prefix="/agent", tags=["agent"])


class PlanRequest(SQLModel):
    instruction: str
    screen: Optional[str] = None


class BriefRequest(SQLModel):
    goal: str
    model: Literal["claude", "local"] = "local"


class McpRequest(SQLModel):
    goal: str
    model: Literal["local"] = "local"  # MCP 에이전트는 로컬(Ollama) 기준


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


@router.post("/brief")
def agent_brief(req: BriefRequest):
    """자율 다단계 브리핑 에이전트 — 목표를 받아 여러 조회 도구를 스스로 연쇄 실행하고,
    각 단계(도구 호출·결과)를 SSE로 흘린 뒤 구조화된 브리핑으로 종합한다. (읽기 전용)

    쿠키 경로(만료 가능)를 건너뛰고 run_local/run_claude를 직접 써서 브리핑 프롬프트를 주입한다.
    """
    from ..chat.providers import AGENT_BRIEF_PROMPT, run_claude, run_local

    def event_stream():
        msgs = [{"role": "user", "content": req.goal}]
        runner = run_local if req.model == "local" else run_claude
        for event in runner(msgs, system_prompt=AGENT_BRIEF_PROMPT):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/mcp")
async def agent_mcp(req: McpRequest):
    """MCP 클라이언트 에이전트(SSE) — MCP 서버에서 도구를 동적 발견해 호출하며 목표 수행.

    우리 ERP를 MCP '서버'로 노출한 것과 대칭: 여기선 에이전트가 MCP '클라이언트'가 된다.
    """
    from ..mcp_client import run_mcp_agent

    async def event_stream():
        async for event in run_mcp_agent(req.goal, req.model):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
