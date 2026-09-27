"""RAG·에이전트 라우팅 eval 하네스.

골든셋(golden.jsonl)의 각 질문을 에이전트에 통과시켜 채점한다:
  - 근거 경로(web/doc/db/none)가 기대와 맞는지  ← 이 시스템의 핵심 계약
  - 답변에 기대 문구가 포함/미포함인지(선택)

'답변 텍스트'가 아니라 '어떤 근거로 답했나'를 채점하므로, 모델이 흔들려도
라우팅 회귀(예: 웹 질문에 사내 문서가 딸려오는 근거 오염)를 안정적으로 잡는다.

실행 (백엔드 DB + Ollama 필요):
    cd backend && ../.venv/bin/python eval/run_eval.py
    EVAL_MODEL=local python eval/run_eval.py   # 기본 local

종료코드: 전부 통과 0, 하나라도 실패 1 (CI 연결용).
"""
import json
import os
import sys
from pathlib import Path

# app 패키지 임포트를 위해 backend 디렉터리를 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.chat.providers import run_chat  # noqa: E402

DB_TOOLS = {"get_dashboard", "get_inventory", "list_orders", "list_partners"}
DOC_TOOLS = {"doc_context", "search_documents"}
WEB_TOOLS = {"web_search"}


def categorize(tools: list[str]) -> set[str]:
    cats: set[str] = set()
    for t in tools:
        if t in WEB_TOOLS:
            cats.add("web")
        elif t in DOC_TOOLS:
            cats.add("doc")
        elif t in DB_TOOLS:
            cats.add("db")
    return cats


def run_one(model: str, question: str) -> tuple[list[str], str]:
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


def main() -> int:
    model = os.getenv("EVAL_MODEL", "local")
    path = Path(__file__).with_name("golden.jsonl")
    cases = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    print(f"\n== RAG·에이전트 라우팅 eval  (model={model}, n={len(cases)}) ==\n")
    print(f"{'id':<20}{'결과':<6}{'기대':<6}{'실제':<12}{'라우팅':<8}{'내용':<6}미리보기")
    print("-" * 92, flush=True)

    passed = 0
    route_ok_n = 0
    for c in cases:
        tools, ans = run_one(model, c["question"])
        cats = categorize(tools)
        exp = c["expect_source"]
        routing_ok = (len(cats) == 0) if exp == "none" else (exp in cats)
        content_ok = all(s in ans for s in c.get("expect_contains", [])) and all(
            s not in ans for s in c.get("expect_not_contains", [])
        )
        ok = routing_ok and content_ok
        passed += ok
        route_ok_n += routing_ok
        preview = ans.replace("\n", " ")[:56]
        print(
            f"{c['id']:<20}{'✅' if ok else '❌':<5} {exp:<6}{','.join(sorted(cats) or ['none']):<12}"
            f"{'✓' if routing_ok else '✗':<8}{'✓' if content_ok else '✗':<6}{preview}",
            flush=True,
        )
    pct = round(100 * passed / len(cases)) if cases else 0
    rpct = round(100 * route_ok_n / len(cases)) if cases else 0
    print("-" * 92)
    print(f"\n종합: {passed}/{len(cases)} 통과 ({pct}%)  ·  라우팅 정확도 {route_ok_n}/{len(cases)} ({rpct}%)\n")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
