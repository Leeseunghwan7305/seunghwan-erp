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


def _doc_context(messages: list[dict], min_score: float | None = None) -> str:
    """최근 사용자 질문으로 문서를 미리 검색해 시스템 프롬프트에 붙일 근거 블록.

    min_score를 주면 그 임계값으로 검색한다(도움말 도우미는 낮춰서 더 잘 찾게 함).
    """
    from ..rag.retrieval import context_for

    text = _last_user_text(messages)
    return context_for(text) if min_score is None else context_for(text, min_score=min_score)


# 엄격 근거 모드: 문서도 도구도 근거로 쓰지 않고 모델이 자기 지식으로만 답하는 것을 막는다.
# (RAG_STRICT=false 로 끌 수 있음)
STRICT_GROUNDING = os.getenv("RAG_STRICT", "true").lower() == "true"
NO_GROUND_MSG = "문서에서 찾을 수 없습니다."


def _guard_answer(text: str, has_doc: bool, used_tool: bool) -> str:
    """근거(문서 주입/도구 호출)가 하나도 없으면 자체 지식 답변을 막고 정형 문구로 대체."""
    if STRICT_GROUNDING and not has_doc and not used_tool:
        return NO_GROUND_MSG
    return text


def _web_fallback_context(query: str) -> str:
    """모델이 근거 없이 거부하려 할 때, 백엔드가 직접 web_search를 돌려 만든 근거 블록.

    작은 로컬 모델은 web_search 도구를 스스로 잘 못 부른다. 그래서 '근거 없음'으로
    거부하기 직전에 서버가 검색을 대신 실행하고, 그 결과를 문서 근거처럼 주입해
    한 번 더 답하게 한다. 결과가 없으면 ''을 돌려 기존 거부로 폴백한다.
    """
    q = (query or "").strip()
    if not q:
        return ""
    res = execute_tool("web_search", {"query": q})
    if not isinstance(res, list) or not res:
        return ""
    lines = ["\n\n# 웹 검색 결과 (이 내용에만 근거해 답하고, 답 끝에 '(출처: 웹 검색)'을 붙여라)"]
    for h in res[:5]:
        lines.append(f"- {h.get('제목', '')}: {h.get('요약', '')}")
    return "\n".join(lines)

# ── RAG 에이전트 정체성 / 리즈닝 / 규칙 ───────────────────────────────────
# 세 조각으로 나눠 쿠키 provider(_PREAMBLE)와 공유한다. '수동적 RAG'가 아니라
# 스스로 의도를 분류하고 도구를 골라 근거를 모은 뒤 자기점검하는 '에이전트'로 동작시킨다.

AGENT_IDENTITY = (
    "너는 '원장(元帳)'이라는 이름의 제조·유통 ERP 운영 에이전트다. "
    "프로젝트의 '물류 원장'을 지키는 실무 담당자처럼, 사용자의 업무 질문을 스스로 분석해 "
    "어떤 근거가 필요한지 판단하고, 알맞은 도구를 골라 근거를 확보한 뒤, 그 근거만으로 "
    "정확하게 답하는 것이 너의 임무다. 정중하지만 군더더기 없이, 사실에 충실하라.\n"
)

# 리즈닝 절차: '답을 바로 쓰지 말고, 먼저 판단하라'는 에이전트의 핵심.
REASONING_FRAMEWORK = (
    "\n# 사고 절차 (매 질문마다 속으로 따르되, 과정은 출력하지 마라)\n"
    "1) 의도 분류 — 질문이 무엇을 원하나? "
    "(a) 실시간 ERP 수치  (b) 사내 규정·정의·절차  (c) 외부 최신 정보  (d) 단순 대화\n"
    "2) 근거 계획 — 그 답을 뒷받침할 근거를 '어떤 도구로' 얻을지 정하라.\n"
    "   · (a) → get_dashboard/get_inventory/list_orders/list_partners (라이브 조회, 출처 없음)\n"
    "   · (b) → 아래 '참고 문서'(자동 주입) 또는 search_documents (답 끝에 '(출처: 제목)')\n"
    "   · (c) → web_search (답 끝에 '(출처: 웹 검색)')\n"
    "3) 실행 — 계획한 도구를 호출해 근거를 확보하라. 필요하면 여러 개를 이어서 써도 된다.\n"
    "4) 자기 점검 — 확보한 근거가 답하기에 충분한가? 부족하거나 어긋나면 도구를 한 번 더 불러 보완하라.\n"
    "5) 답변 — 확보한 근거만으로 답하라. 근거가 없으면 지어내지 말고 '문서에서 찾을 수 없습니다'.\n"
)

AGENT_RULES = (
    "\n# 규칙\n"
    "- 재고 수량·주문 내역·매출/미수금/미지급금 등 실시간 현황은 문서가 아니라 반드시 도구로 "
    "라이브 조회하라(이때는 출처를 붙이지 마라).\n"
    "- 사내 규정·정의·절차는 참고 문서/문서 도구를 근거로 하고, 문서의 값(숫자 포함)은 그대로 "
    "쓰며 답 끝에 줄을 바꿔 '(출처: 문서제목)'을 표기하라.\n"
    "- 사내 문서·ERP 데이터로 답할 수 없는 외부 정보(시세·환율·시사·일반 용어 정의 등)는 지어내지 "
    "말고 반드시 web_search로 검색해 근거에 두고, 답 끝에 '(출처: 웹 검색)'을 표기하라.\n"
    "- 문서에도 없고, ERP 도구로도, web_search로도 얻을 수 없을 때만 '문서에서 찾을 수 없습니다'라고 답하라.\n"
    "- 추측 금지. 금액은 원(₩) 단위로 읽기 쉽게 표시하라. 한국어로 간결하게 답하라."
)

SYSTEM_PROMPT = AGENT_IDENTITY + REASONING_FRAMEWORK + AGENT_RULES

MAX_TOOL_ROUNDS = 6

# Claude 전용: 답변을 '답 + 출처'로만. 군더더기 금지.
CLAUDE_TERSE = (
    "\n- 답변은 '질문에 대한 답'과 '(출처: 제목)'만 출력하라. 인사·되묻기·부연 설명·"
    "주의 문구 등 군더더기는 절대 붙이지 마라."
)


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

def run_claude(messages: list[dict], model: str | None = None, doc_min_score: float | None = None) -> Iterator[dict]:
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
    doc_ctx = _doc_context(messages, doc_min_score)
    has_doc = bool(doc_ctx)
    used_tool = False
    system = SYSTEM_PROMPT + CLAUDE_TERSE + doc_ctx
    conv = [{"role": m["role"], "content": m["content"]} for m in messages]
    if has_doc:
        yield {"type": "tool", "name": "doc_context"}  # 문서 근거 자동 주입됨(출처 표시용)

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
            if STRICT_GROUNDING and not has_doc and not used_tool:
                q = _last_user_text(messages)
                web = _web_fallback_context(q)
                if web:
                    yield {"type": "tool", "name": "web_search", "input": {"query": q}}
                    try:
                        resp2 = client.messages.create(
                            model=model, max_tokens=1024, temperature=0,
                            system=SYSTEM_PROMPT + CLAUDE_TERSE + web,
                            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
                        )
                        text = "".join(b.text for b in resp2.content if b.type == "text")
                    except Exception as e:  # noqa: BLE001
                        yield {"type": "error", "content": f"웹 검색 후 답변 오류: {e}"}
                        return
                    yield {"type": "text", "content": text or NO_GROUND_MSG}
                    yield {"type": "done"}
                    return
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

def run_local(messages: list[dict], model: str | None = None, doc_min_score: float | None = None) -> Iterator[dict]:
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = model or os.getenv("OLLAMA_MODEL", "qwen2.5")
    doc_ctx = _doc_context(messages, doc_min_score)
    has_doc = bool(doc_ctx)
    used_tool = False
    conv: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT + doc_ctx}]
    conv += [{"role": m["role"], "content": m["content"]} for m in messages]
    if has_doc:
        yield {"type": "tool", "name": "doc_context"}  # 문서 근거 자동 주입됨(출처 표시용)

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
            content = msg.get("content", "")
            if STRICT_GROUNDING and not has_doc and not used_tool:
                q = _last_user_text(messages)
                web = _web_fallback_context(q)
                if web:
                    yield {"type": "tool", "name": "web_search", "input": {"query": q}}
                    try:
                        r2 = httpx.post(
                            f"{base}/api/chat",
                            json={
                                "model": model,
                                "messages": [{"role": "system", "content": SYSTEM_PROMPT + web}]
                                + [{"role": m["role"], "content": m["content"]} for m in messages],
                                "stream": False,
                                "options": {"temperature": 0},
                            },
                            timeout=120.0,
                        )
                        r2.raise_for_status()
                        content = r2.json().get("message", {}).get("content", "")
                    except Exception as e:  # noqa: BLE001
                        yield {"type": "error", "content": f"웹 검색 후 답변 오류: {e}"}
                        return
                    yield {"type": "text", "content": content or NO_GROUND_MSG}
                    yield {"type": "done"}
                    return
            yield {"type": "text", "content": _guard_answer(content, has_doc, used_tool)}
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


def run_chat(
    model_choice: str, messages: list[dict], doc_min_score: float | None = None
) -> Iterator[dict]:
    """model_choice: 'claude' | 'local'

    'claude'는 CLAUDE_SESSION_KEY(구독 쿠키)가 있으면 쿠키 provider를,
    없으면 공식 API provider(ANTHROPIC_API_KEY)를 사용한다.
    doc_min_score: 문서 자동검색 임계값 override(도움말 도우미는 낮게 줘서 SOP를 더 잘 찾음).
    """
    if model_choice == "local":
        yield from run_local(messages, doc_min_score=doc_min_score)
    elif os.getenv("CLAUDE_SESSION_KEY", "").strip():
        from .claude_cookie import run_claude_cookie
        yield from run_claude_cookie(messages)
    else:
        yield from run_claude(messages, doc_min_score=doc_min_score)
