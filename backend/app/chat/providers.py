"""모델 라우팅: Claude / 로컬(Ollama)을 공통 인터페이스로 다룬다.

각 provider는 (model, messages)를 받아 이벤트를 순차적으로 yield 하는 제너레이터다.
이벤트 종류:
  {"type": "tool",  "name": str, "input": dict}   # 도구 호출 시작
  {"type": "text",  "content": str}                # 최종 답변 텍스트
  {"type": "error", "content": str}                # 오류
  {"type": "done"}                                 # 종료
"""
import json
import os
from typing import Any, Iterator

import httpx

from .tools import TOOL_DEFS, execute_tool


def _last_user_text(messages: list[dict]) -> str:
    """대화에서 가장 최근 사용자 발화를 찾는다(자동 문서 검색용)."""
    return next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"),
        "",
    )


def _doc_context(messages: list[dict]) -> str:
    """최근 사용자 질문으로 문서를 미리 검색해 시스템 프롬프트에 붙일 근거 블록."""
    from ..rag.retrieval import context_for

    return context_for(_last_user_text(messages))


# 엄격 근거 모드: 문서도 도구도 근거로 쓰지 않고 모델이 자기 지식으로만 답하는 것을 막는다.
# (RAG_STRICT=false 로 끌 수 있음)
STRICT_GROUNDING = os.getenv("RAG_STRICT", "true").lower() == "true"
NO_GROUND_MSG = "문서에서 찾을 수 없습니다."


def _guard_answer(text: str, has_doc: bool, used_tool: bool) -> str:
    """근거(문서 주입/도구 호출)가 하나도 없으면 자체 지식 답변을 막고 정형 문구로 대체."""
    if STRICT_GROUNDING and not has_doc and not used_tool:
        return NO_GROUND_MSG
    return text

SYSTEM_PROMPT = (
    "너는 제조 ERP의 업무 보조 AI다.\n"
    "- 아래 '참고 문서'에 질문의 답이 있으면 반드시 그 문서 내용을 근거로 답하라. 문서에 적힌 "
    "숫자(나이·가격 등)도 그대로 문서 값을 쓰고, 답변 맨 끝에 줄을 바꿔 '(출처: 문서제목)'을 표기하라.\n"
    "- 재고 수량·주문 내역·매출/미수금/미지급금 등 실시간 ERP 운영 현황은 문서가 아니라 반드시 "
    "도구(get_dashboard, get_inventory, list_orders, list_partners)로 라이브 조회해 답하라. "
    "이때는 출처를 붙이지 마라.\n"
    "- 문서에 적힌 내용만 사용하고, 문서에 없는 배경지식·정의·수치를 지어내 덧붙이지 마라. "
    "문서에도 없고 도구로도 얻을 수 없는 것은 지어내지 말고 '문서에서 찾을 수 없습니다'라고만 답하라.\n"
    "- 추측 금지. 금액은 원(₩) 단위로 읽기 쉽게 표시하라. 한국어로 간결하게 답하라."
)

MAX_TOOL_ROUNDS = 6


# ---- 도구 스키마 변환 -----------------------------------------------------

def _claude_tools() -> list[dict]:
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
        for t in TOOL_DEFS
    ]


def _ollama_tools() -> list[dict]:
    return [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
        for t in TOOL_DEFS
    ]


# ---- Claude --------------------------------------------------------------

def run_claude(messages: list[dict], model: str | None = None) -> Iterator[dict]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        yield {"type": "error", "content": "ANTHROPIC_API_KEY가 설정되지 않았습니다. 프로젝트 루트 .env에 키를 넣고 백엔드를 재시작하세요."}
        return

    try:
        from anthropic import Anthropic
    except ImportError:
        yield {"type": "error", "content": "anthropic 패키지가 설치되지 않았습니다."}
        return

    client = Anthropic(api_key=api_key)
    model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
    doc_ctx = _doc_context(messages)
    has_doc = bool(doc_ctx)
    used_tool = False
    system = SYSTEM_PROMPT + doc_ctx
    conv = [{"role": m["role"], "content": m["content"]} for m in messages]

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=1024,
                temperature=0,
                system=system,
                tools=_claude_tools(),
                messages=conv,
            )
        except Exception as e:  # noqa: BLE001
            yield {"type": "error", "content": f"Claude 호출 오류: {e}"}
            return

        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if not tool_uses:
            text = "".join(b.text for b in resp.content if b.type == "text")
            yield {"type": "text", "content": _guard_answer(text, has_doc, used_tool)}
            yield {"type": "done"}
            return

        used_tool = True
        conv.append({"role": "assistant", "content": [b.model_dump() for b in resp.content]})
        results = []
        for tu in tool_uses:
            yield {"type": "tool", "name": tu.name, "input": tu.input}
            result = execute_tool(tu.name, tu.input)
            results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
        conv.append({"role": "user", "content": results})

    yield {"type": "error", "content": "도구 호출 한도를 초과했습니다."}


# ---- 로컬 (Ollama) --------------------------------------------------------

def run_local(messages: list[dict], model: str | None = None) -> Iterator[dict]:
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = model or os.getenv("OLLAMA_MODEL", "qwen2.5")
    doc_ctx = _doc_context(messages)
    has_doc = bool(doc_ctx)
    used_tool = False
    conv: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT + doc_ctx}]
    conv += [{"role": m["role"], "content": m["content"]} for m in messages]

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            r = httpx.post(
                f"{base}/api/chat",
                json={
                    "model": model,
                    "messages": conv,
                    "tools": _ollama_tools(),
                    "stream": False,
                    # 문서 밖 내용을 지어내거나 섞지 않도록 결정적으로.
                    "options": {"temperature": 0},
                },
                timeout=120.0,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.ConnectError:
            yield {"type": "error", "content": f"Ollama 서버에 연결할 수 없습니다({base}). 'ollama serve'로 실행하세요."}
            return
        except Exception as e:  # noqa: BLE001
            yield {"type": "error", "content": f"로컬 LLM 호출 오류: {e}"}
            return

        msg = data.get("message", {})
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            yield {"type": "text", "content": _guard_answer(msg.get("content", ""), has_doc, used_tool)}
            yield {"type": "done"}
            return

        used_tool = True
        conv.append(msg)
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            yield {"type": "tool", "name": name, "input": args}
            result = execute_tool(name, args)
            conv.append({"role": "tool", "content": json.dumps(result, ensure_ascii=False)})

    yield {"type": "error", "content": "도구 호출 한도를 초과했습니다."}


def run_chat(model_choice: str, messages: list[dict]) -> Iterator[dict]:
    """model_choice: 'claude' | 'local'

    'claude'는 CLAUDE_SESSION_KEY(구독 쿠키)가 있으면 쿠키 provider를,
    없으면 공식 API provider(ANTHROPIC_API_KEY)를 사용한다.
    """
    if model_choice == "local":
        yield from run_local(messages)
    elif os.getenv("CLAUDE_SESSION_KEY", "").strip():
        from .claude_cookie import run_claude_cookie
        yield from run_claude_cookie(messages)
    else:
        yield from run_claude(messages)
