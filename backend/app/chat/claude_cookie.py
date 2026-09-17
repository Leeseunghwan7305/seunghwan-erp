"""쿠키 기반 Claude provider — claude.ai 웹 세션을 그대로 재사용해 호출한다.

공식 Messages API(ANTHROPIC_API_KEY, 사용량 과금) 대신, 브라우저에서 로그인한
claude.ai 세션 쿠키(sessionKey 등)로 내부 API를 호출한다. 구독료 외 추가 과금이 없다.

한계 / 주의
- claude.ai 웹 세션엔 공식 API의 tool_use(함수 호출) 인터페이스가 없다. 그래서
  도구는 "프롬프트 에뮬레이션"으로 처리한다: 도구 목록·JSON 액션 규약을 프롬프트에
  주입하고, Claude가 뱉은 JSON을 파싱해 실행한 뒤 결과를 대화에 다시 넣는 ReAct 루프.
- 내부 API/SSE 포맷은 예고 없이 바뀔 수 있고, 프로그래밍 호출은 Anthropic ToS 위반
  소지가 있다. 본인 계정 자동화 용도로만 사용한다. 깨지면 쿠키 갱신 또는 코드 조정 필요.

이벤트 스트림은 다른 provider와 동일하다:
  {"type": "tool", "name": str, "input": dict}
  {"type": "text", "content": str}
  {"type": "error", "content": str}
  {"type": "done"}
"""
import json
import os
import re
import time
import uuid
from typing import Iterator, Optional

import httpx

from .tools import execute_tool, tools_prompt

MAX_TOOL_ROUNDS = 6
# 대화의 첫 메시지 부모로 쓰는 claude.ai 루트 UUID (내부 API 관례값).
_ROOT_PARENT = "00000000-0000-4000-8000-000000000000"

# 429(rate limit) 대응
_MAX_429_RETRIES = 3
_BACKOFF_BASE = 3.0   # 초; Retry-After 헤더가 없을 때 3, 6, 12초로 대기
_BACKOFF_CAP = 20.0   # 초; 한 번 대기 상한
_INTER_ROUND_DELAY = 2.5   # 초; ReAct 라운드 사이 선제 지연


def _retry_after_seconds(resp: httpx.Response, attempt: int) -> float:
    """Retry-After 헤더가 있으면 그 값을, 없으면 지수 백오프를 반환(상한 적용)."""
    ra = resp.headers.get("retry-after")
    if ra:
        try:
            return min(float(ra), _BACKOFF_CAP)
        except ValueError:
            pass
    return min(_BACKOFF_BASE * (2 ** attempt), _BACKOFF_CAP)

_PREAMBLE = (
    "너는 제조 ERP의 업무 보조 AI다.\n"
    "- 아래 '참고 문서'에 질문의 답이 있으면 반드시 그 문서 내용을 근거로 답하고(숫자도 문서 값 그대로) "
    "답변 맨 끝에 '(출처: 문서제목)'을 표기하라.\n"
    "- 재고·주문·매출/미수금/미지급금 등 실시간 ERP 운영 현황은 문서가 아니라 아래 도구로 조회해 답하라(출처 없음).\n"
    "- 문서에도 없고 도구로도 얻을 수 없으면 지어내지 말고 '문서에서 찾을 수 없습니다'라고만 답하라.\n"
    "- 답변은 '질문에 대한 답'과 '(출처: 제목)'만 출력하라. 인사·되묻기·부연 설명·주의 문구·"
    "군더더기는 절대 붙이지 마라. 금액은 원(₩) 단위, 한국어로 간결히.\n\n"
)


# ---- 쿠키 / 헤더 ----------------------------------------------------------

def _load_cookies() -> Optional[dict]:
    """.env에서 claude.ai 쿠키를 읽는다. sessionKey가 없으면 None."""
    session_key = os.getenv("CLAUDE_SESSION_KEY", "").strip()
    if not session_key:
        return None
    cookies = {"sessionKey": session_key}
    for env_name, cookie_name in (
        ("CLAUDE_CF_CLEARANCE", "cf_clearance"),
        ("CLAUDE_CF_BM", "__cf_bm"),
    ):
        val = os.getenv(env_name, "").strip()
        if val:
            cookies[cookie_name] = val
    return cookies


def _cookie_header(cookies: dict) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def _headers(cookies: dict) -> dict:
    return {
        "Cookie": _cookie_header(cookies),
        "Content-Type": "application/json",
        "Accept": "text/event-stream, application/json",
        "Origin": "https://claude.ai",
        "Referer": "https://claude.ai/",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
        ),
    }


# ---- 도구 호출 파싱 -------------------------------------------------------

def _extract_tool_call(text: str) -> Optional[dict]:
    """응답 텍스트에서 {"tool": ..., "input": ...} JSON을 관대하게 추출한다.

    ```json 펜스나 산문에 섞여 있어도 첫 번째 유효한 tool JSON을 찾는다.
    """
    # 1) ```json ... ``` 펜스 우선
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = []
    if fence:
        candidates.append(fence.group(1))
    # 2) 본문에서 중괄호 균형을 맞춰 후보 추출
    candidates.extend(_balanced_objects(text))

    for cand in candidates:
        try:
            obj = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "tool" in obj:
            return {"name": obj["tool"], "input": obj.get("input") or {}}
    return None


def _balanced_objects(text: str) -> list[str]:
    """텍스트에서 최상위 중괄호 객체들을 순서대로 뽑아 문자열 리스트로 반환."""
    out, depth, start = [], 0, -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    out.append(text[start : i + 1])
    return out


# ---- SSE 텍스트 추출 ------------------------------------------------------

def _extract_delta(obj: dict) -> str:
    """claude.ai SSE 한 이벤트에서 텍스트 조각을 뽑는다(포맷 변화 대응)."""
    if not isinstance(obj, dict):
        return ""
    if isinstance(obj.get("completion"), str):
        return obj["completion"]
    delta = obj.get("delta")
    if isinstance(delta, dict) and isinstance(delta.get("text"), str):
        return delta["text"]
    if isinstance(obj.get("text"), str):
        return obj["text"]
    return ""


# ---- claude.ai 호출 -------------------------------------------------------

def _get_org_id(client: httpx.Client) -> str:
    """CLAUDE_ORG_ID가 없으면 /api/organizations에서 첫 조직을 가져온다."""
    org_id = os.getenv("CLAUDE_ORG_ID", "").strip()
    if org_id:
        return org_id
    r = client.get("https://claude.ai/api/organizations")
    r.raise_for_status()
    orgs = r.json()
    if not orgs:
        raise RuntimeError("claude.ai 조직을 찾을 수 없습니다.")
    return orgs[0]["uuid"]


def _create_conversation(client: httpx.Client, org_id: str) -> str:
    conv_uuid = str(uuid.uuid4())
    r = client.post(
        f"https://claude.ai/api/organizations/{org_id}/chat_conversations",
        json={"uuid": conv_uuid, "name": ""},
    )
    r.raise_for_status()
    return r.json().get("uuid", conv_uuid)


def _extract_msg_uuid(obj: dict) -> Optional[str]:
    """SSE 이벤트에서 assistant 메시지 uuid를 best-effort로 뽑는다.

    다음 라운드의 parent_message_uuid로 넘겨 대화 트리를 올바르게 잇기 위함.
    포맷이 달라도 실패하면 None → 상위에서 루트로 폴백한다.
    """
    for key in ("id", "message_id", "uuid", "parent_message_uuid"):
        v = obj.get(key)
        if isinstance(v, str) and v:
            return v
    msg = obj.get("message")
    if isinstance(msg, dict):
        v = msg.get("uuid") or msg.get("id")
        if isinstance(v, str) and v:
            return v
    return None


def _completion(
    client: httpx.Client, org_id: str, conv_id: str, prompt: str, parent_uuid: str
) -> tuple[str, str]:
    """한 번의 completion을 호출하고 (전체 응답 텍스트, 이 응답 메시지 uuid)를 반환한다.

    ReAct 루프에서 '도구 호출 vs 최종 답변'을 판별하려면 한 라운드 텍스트를
    끝까지 받아야 하므로, 스트리밍 델타를 누적해 문자열로 돌려준다. 메시지 uuid는
    다음 라운드의 parent로 쓰며, 못 잡으면 받은 parent_uuid를 그대로 유지한다.
    """
    payload = {
        "prompt": prompt,
        "parent_message_uuid": parent_uuid,
        "timezone": os.getenv("CLAUDE_TIMEZONE", "Asia/Seoul"),
        "attachments": [],
        "files": [],
        "rendering_mode": "messages",
    }
    url = f"https://claude.ai/api/organizations/{org_id}/chat_conversations/{conv_id}/completion"
    for attempt in range(_MAX_429_RETRIES + 1):
        parts: list[str] = []
        msg_uuid = parent_uuid
        with client.stream("POST", url, json=payload) as resp:
            if resp.status_code == 429 and attempt < _MAX_429_RETRIES:
                resp.read()  # 스트림 소비(커넥션 정리)
                time.sleep(_retry_after_seconds(resp, attempt))
                continue
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                parts.append(_extract_delta(obj))
                msg_uuid = _extract_msg_uuid(obj) or msg_uuid
        return "".join(parts).strip(), msg_uuid
    # 재시도 소진: 마지막으로 한 번 더 시도해 429를 그대로 올려 상위에서 처리
    resp = client.post(url, json=payload)
    resp.raise_for_status()
    return "", parent_uuid


# ---- 엔트리포인트 ---------------------------------------------------------

def run_claude_cookie(messages: list[dict]) -> Iterator[dict]:
    cookies = _load_cookies()
    if cookies is None:
        yield {
            "type": "error",
            "content": "CLAUDE_SESSION_KEY가 없습니다. claude.ai 로그인 후 sessionKey 쿠키를 "
            "루트 .env에 넣고 백엔드를 재시작하세요.",
        }
        return

    # 첫 프롬프트: 프리앰블 + 자동 문서 검색 근거 + 도구 규약 + 지금까지의 대화 이력
    from ..rag.retrieval import context_for

    from .providers import _guard_answer

    last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    doc_ctx = context_for(last_user)
    has_doc = bool(doc_ctx)
    used_tool = False
    history = "\n".join(
        f"{'사용자' if m['role'] == 'user' else 'AI'}: {m['content']}" for m in messages
    )
    prompt = _PREAMBLE + doc_ctx + tools_prompt() + "\n\n---\n" + history

    try:
        with httpx.Client(headers=_headers(cookies), timeout=120.0) as client:
            org_id = _get_org_id(client)
            conv_id = _create_conversation(client, org_id)

            parent = _ROOT_PARENT
            for _ in range(MAX_TOOL_ROUNDS):
                text, parent = _completion(client, org_id, conv_id, prompt, parent)
                call = _extract_tool_call(text)
                if not call:
                    yield {"type": "text", "content": _guard_answer(text, has_doc, used_tool)}
                    yield {"type": "done"}
                    return
                used_tool = True
                yield {"type": "tool", "name": call["name"], "input": call["input"]}
                result = execute_tool(call["name"], call["input"])
                time.sleep(_INTER_ROUND_DELAY)  # 연속 completion 버스트 완화(429 예방)
                prompt = (
                    f"도구 {call['name']} 결과(JSON):\n"
                    + json.dumps(result, ensure_ascii=False)
                    + "\n\n이 결과로 최종 답변하거나, 필요하면 도구를 한 번 더 호출하라."
                )
            yield {"type": "error", "content": "도구 호출 한도를 초과했습니다."}
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        if code in (401, 403):
            yield {
                "type": "error",
                "content": "claude.ai 인증 실패(쿠키 만료 가능). sessionKey/cf_clearance를 갱신하세요.",
            }
        elif code == 429:
            yield {
                "type": "error",
                "content": "claude.ai 요청이 제한됐습니다(HTTP 429). 잠시 후 다시 시도하거나, "
                ".env에 CLAUDE_CF_CLEARANCE·CLAUDE_CF_BM 쿠키를 추가하면 Cloudflare 제한을 줄일 수 있습니다.",
            }
        else:
            yield {"type": "error", "content": f"claude.ai 호출 오류(HTTP {code})."}
    except httpx.ConnectError:
        yield {"type": "error", "content": "claude.ai에 연결할 수 없습니다(네트워크 확인)."}
    except Exception as e:  # noqa: BLE001 - 프로토타입: 오류를 사용자에게 노출
        yield {"type": "error", "content": f"쿠키 Claude 호출 오류: {e}"}
