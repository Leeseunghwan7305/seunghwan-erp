"""자가 개선 루프 — eval 골든셋을 돌려 라우팅 회귀를 찾고, LLM이 스스로
근본 원인을 진단하고 고칠 레버(임계값·프롬프트·웹폴백)를 제안하게 한다.

핵심: 평가는 '답변 텍스트'가 아니라 '어떤 근거 경로(web/doc/db/none)로 답했나'를
채점한다(라우팅 계약). 그 계약을 깨는 케이스를 모아 메타-추론 LLM에 넘겨,
사람이 적용할 만한 구체적 수정안을 받는다. 전부 통과면 '어디가 취약한지 +
어떤 엣지 케이스를 골든셋에 추가할지'를 제안하게 해 루프가 늘 유용하도록 한다.

읽기 전용: 코드를 자동 수정하지 않는다(제안만). 적용은 사람이 판단한다.
"""
import json
import os
from pathlib import Path
from typing import Any, Iterator

import httpx

from ..chat.providers import run_chat

DB_TOOLS = {"get_dashboard", "get_inventory", "list_orders", "list_partners"}
DOC_TOOLS = {"doc_context", "search_documents"}
WEB_TOOLS = {"web_search"}

GOLDEN = Path(__file__).resolve().parents[2] / "eval" / "golden.jsonl"


def _categorize(tools: list[str]) -> set[str]:
    cats: set[str] = set()
    for t in tools:
        if t in WEB_TOOLS:
            cats.add("web")
        elif t in DOC_TOOLS:
            cats.add("doc")
        elif t in DB_TOOLS:
            cats.add("db")
    return cats


def _run_one(model: str, question: str) -> tuple[list[str], str]:
    tools: list[str] = []
    text: list[str] = []
    for evt in run_chat(model, [{"role": "user", "content": question}]):
        kind = evt.get("type")
        if kind == "tool":
            tools.append(evt["name"])
        elif kind == "text":
            text.append(evt.get("content", ""))
        elif kind == "error":
            text.append("[error] " + evt.get("content", ""))
    return tools, "".join(text)


# 진단 LLM이 알아야 할 '고칠 수 있는 레버'들 — 코드가 실제로 노출하는 손잡이와 일치한다.
LEVERS = """조정 가능한 레버(코드 내 실제 손잡이):
- CONTEXT_MIN_SCORE (providers.py): 문서 자동주입 임계값. 낮추면 문서가 더 잘 붙지만 '근거 오염'(웹 질문에 사내 문서가 딸려옴) 위험↑, 높이면 반대.
- SYSTEM_PROMPT / 라우팅 규칙 (providers.py): 언제 DB/문서/웹을 쓸지 모델에 주는 지침.
- STRICT_GROUNDING 웹폴백 (providers.py): 근거 없이 자기지식으로 답하려 할 때 서버가 대신 웹검색을 돌림.
- 골든셋 (eval/golden.jsonl): 계약을 고정하는 회귀 케이스."""

DIAGNOSE_SYSTEM = (
    "너는 RAG 라우팅 시스템의 품질 엔지니어다. 아래 eval 결과를 보고 한국어로 진단한다. "
    "장황한 서론 없이 바로 핵심만. 마크다운으로 간결하게.\n\n" + LEVERS + "\n\n"
    "형식:\n"
    "## 진단\n"
    "- (실패가 있으면) 각 실패의 근본 원인을 한 줄로. 실패가 없으면 현재 가장 취약한 지점 1~2개.\n"
    "## 제안 (우선순위 순)\n"
    "- 어떤 레버를 어떻게 바꿀지 **구체적 값/문구**까지. 각 제안에 기대 효과와 부작용(trade-off)을 붙인다.\n"
    "## 회귀 방어\n"
    "- 골든셋에 추가하면 좋을 엣지 케이스 1~3개(질문 + 기대 근거경로).\n"
)


def _diagnose_prompt(cases: list[dict], results: list[dict]) -> str:
    passed = sum(1 for r in results if r["ok"])
    fails = [r for r in results if not r["ok"]]
    lines = [f"전체 {len(results)}개 중 {passed}개 통과, {len(fails)}개 실패.\n"]
    if fails:
        lines.append("실패 케이스:")
        for r in fails:
            lines.append(
                f"- [{r['id']}] 질문: {r['question']!r}\n"
                f"  기대 근거={r['expect']}, 실제 근거={r['actual'] or 'none'}, "
                f"라우팅={'OK' if r['routing_ok'] else 'X'}, 내용={'OK' if r['content_ok'] else 'X'}\n"
                f"  답변 미리보기: {r['preview']!r}"
            )
    else:
        lines.append("실패는 없다. 통과한 케이스 목록(계약):")
        for r in results:
            lines.append(f"- [{r['id']}] {r['question']!r} → 기대 근거={r['expect']}")
    return "\n".join(lines)


def _diagnose_stream(prompt: str, model: str) -> Iterator[dict]:
    """진단은 도구 없는 순수 생성 — Ollama /api/chat를 tools 없이 직접 호출한다.
    (run_local은 ReAct 도구 루프라 메타-추론에는 부적합)"""
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ol_model = model if model.startswith("qwen") or ":" in model else os.getenv("OLLAMA_MODEL", "qwen2.5")
    try:
        with httpx.stream(
            "POST",
            f"{base}/api/chat",
            json={
                "model": ol_model,
                "messages": [
                    {"role": "system", "content": DIAGNOSE_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                "stream": True,
                "options": {"temperature": 0.2},
            },
            timeout=180.0,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                d = (obj.get("message", {}) or {}).get("content") or ""
                if d:
                    yield {"type": "text", "content": d}
                if obj.get("done"):
                    break
    except httpx.ConnectError:
        yield {"type": "error", "content": f"Ollama 서버에 연결할 수 없습니다({base})."}
    except Exception as e:  # noqa: BLE001
        yield {"type": "error", "content": f"진단 생성 오류: {e}"}


def run_self_improve(model: str = "local") -> Iterator[dict[str, Any]]:
    """골든셋 평가 → 케이스별 pass/fail 스트리밍 → 실패 수집 → LLM 자가 진단·제안."""
    cases = [
        json.loads(ln)
        for ln in GOLDEN.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    yield {"type": "eval_start", "total": len(cases)}

    results: list[dict] = []
    for c in cases:
        tools, ans = _run_one(model, c["question"])
        cats = _categorize(tools)
        exp = c["expect_source"]
        routing_ok = (len(cats) == 0) if exp == "none" else (exp in cats)
        content_ok = all(s in ans for s in c.get("expect_contains", [])) and all(
            s not in ans for s in c.get("expect_not_contains", [])
        )
        ok = routing_ok and content_ok
        row = {
            "id": c["id"],
            "question": c["question"],
            "expect": exp,
            "actual": ",".join(sorted(cats)),
            "routing_ok": routing_ok,
            "content_ok": content_ok,
            "ok": ok,
            "preview": ans.replace("\n", " ")[:120],
        }
        results.append(row)
        yield {"type": "case", **row}

    passed = sum(1 for r in results if r["ok"])
    yield {"type": "eval_done", "passed": passed, "total": len(results)}

    yield {"type": "diagnose_start"}
    yield from _diagnose_stream(_diagnose_prompt(cases, results), model)
    yield {"type": "done"}
