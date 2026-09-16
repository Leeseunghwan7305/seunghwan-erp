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

SYSTEM_PROMPT = (
    "너는 제조 ERP의 업무 보조 AI다. 재고·주문·거래처·정산 관련 질문에 답한다. "
    "수치가 필요하면 반드시 제공된 도구를 사용해 실제 데이터를 조회한 뒤 답하라. "
    "매뉴얼·규정·계약 등 문서 내용에 관한 질문은 search_documents로 사내 지식 문서를 검색해 근거로 삼아라. "
    "추측하지 말고, 금액은 원(₩) 단위로 읽기 쉽게 표시하라. 한국어로 간결하게 답하라."
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
    conv = [{"role": m["role"], "content": m["content"]} for m in messages]

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=_claude_tools(),
                messages=conv,
            )
        except Exception as e:  # noqa: BLE001
            yield {"type": "error", "content": f"Claude 호출 오류: {e}"}
            return

        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if not tool_uses:
            text = "".join(b.text for b in resp.content if b.type == "text")
            yield {"type": "text", "content": text}
            yield {"type": "done"}
            return

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
    conv: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    conv += [{"role": m["role"], "content": m["content"]} for m in messages]

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            r = httpx.post(
                f"{base}/api/chat",
                json={"model": model, "messages": conv, "tools": _ollama_tools(), "stream": False},
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
            yield {"type": "text", "content": msg.get("content", "")}
            yield {"type": "done"}
            return

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
