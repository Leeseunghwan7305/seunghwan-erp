"""MCP 클라이언트 에이전트 — 에이전트가 MCP 서버의 도구를 '발견해서' 사용한다.

우리가 만든 ERP MCP 서버(backend/mcp_server.py)에 stdio로 접속해:
  1) list_tools()로 도구를 런타임에 '동적 발견'하고
  2) LLM(로컬 Ollama)이 그 도구들을 골라 호출하면
  3) call_tool()로 MCP 프로토콜을 통해 실제 실행한다.

하드코딩된 TOOL_DEFS가 아니라 '서버가 알려준 도구'로 움직이므로, 다른 MCP 서버를
꽂아도 그 도구를 바로 쓸 수 있는 상호운용 구조다(=MCP 에이전트화).
"""
import json
import os
import sys
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# 접속할 MCP 서버(현재는 우리 ERP 서버). 외부 서버를 추가하려면 여기에 늘리면 된다.
_MCP_SERVER = Path(__file__).resolve().parent.parent / "mcp_server.py"

MCP_AGENT_PROMPT = (
    "너는 MCP 서버에서 '발견한 도구'만 사용해 목표를 달성하는 에이전트다. "
    "목표에 필요한 도구를 적극적으로(보통 2개 이상) 호출해 데이터를 모은 뒤, "
    "한국어로 간결한 종합 답변을 작성하라. 수치는 도구 결과의 실제 값만 쓰고 지어내지 마라."
)

MAX_ROUNDS = 6


async def run_mcp_agent(goal: str, model: str = "local") -> AsyncIterator[dict]:
    """MCP 도구를 발견·사용해 goal을 수행하고 이벤트를 비동기로 yield 한다."""
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    omodel = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    params = StdioServerParameters(command=sys.executable, args=[str(_MCP_SERVER)])

    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # 1) 도구 동적 발견
                listed = await session.list_tools()
                tools = listed.tools
                yield {"type": "discover", "tools": [t.name for t in tools]}

                ollama_tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description or "",
                            "parameters": t.inputSchema or {"type": "object", "properties": {}},
                        },
                    }
                    for t in tools
                ]

                conv: list[dict[str, Any]] = [
                    {"role": "system", "content": MCP_AGENT_PROMPT},
                    {"role": "user", "content": goal},
                ]

                # 2) 도구 호출 루프 (LLM이 MCP 도구를 선택 → MCP로 실행)
                async with httpx.AsyncClient(timeout=120.0) as http:
                    for _ in range(MAX_ROUNDS):
                        r = await http.post(
                            f"{base}/api/chat",
                            json={
                                "model": omodel,
                                "messages": conv,
                                "tools": ollama_tools,
                                "stream": False,
                                "options": {"temperature": 0},
                            },
                        )
                        r.raise_for_status()
                        msg = r.json().get("message", {}) or {}
                        calls = msg.get("tool_calls") or []

                        if not calls:
                            yield {"type": "text", "content": msg.get("content", "")}
                            yield {"type": "done"}
                            return

                        conv.append(msg)
                        for c in calls:
                            fn = c.get("function", {})
                            name = fn.get("name", "")
                            args = fn.get("arguments", {})
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except json.JSONDecodeError:
                                    args = {}
                            yield {"type": "tool", "name": name, "input": args}

                            # 3) MCP 프로토콜로 실제 호출
                            res = await session.call_tool(name, args)
                            text = res.content[0].text if res.content else ""
                            try:
                                data = json.loads(text)
                            except (json.JSONDecodeError, TypeError):
                                data = text
                            yield {"type": "tool_result", "name": name, "data": data}
                            conv.append({"role": "tool", "content": text})

                yield {"type": "error", "content": "도구 호출 한도를 초과했습니다."}
                yield {"type": "done"}
    except Exception as e:  # noqa: BLE001 - 프로토타입: 오류를 사용자에게 노출
        yield {"type": "error", "content": f"MCP 에이전트 오류: {e}"}
        yield {"type": "done"}
