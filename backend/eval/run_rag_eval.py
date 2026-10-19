"""RAG 검색(retrieval) 품질 eval — 커밋된 fixture로 외부 서비스 없이 돈다.

각 골든 질문에 대해 코사인 top-k 검색을 재현하고 채점한다:
  - expect_keywords: 상위 k개 청크 '본문'에 기대 키워드가 모두 등장하나? (Hit@k · 내용)
  - expect_doc(선택): 최상위(top-1) 문서가 기대 문서인가?            (랭킹 정확도)

retrieval.search()와 동일한 코사인 로직을 fixture 임베딩 위에서 재현하므로,
검색 랭킹·임계값·청크 처리 코드의 '회귀'를 결정적으로 잡는다(Ollama·DB 불필요).

게이트:
    통과율이 RAG_EVAL_MIN(기본 0.8) 미만이면 종료코드 1 → CI·pre-push 훅이 막는다.

실행:
    cd backend && python eval/run_rag_eval.py
    RAG_EVAL_MIN=0.9 python eval/run_rag_eval.py
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "rag_golden.jsonl"
FIXTURE = HERE / "rag_fixture.json"
DEFAULT_MIN = 0.8


def _topk(matrix_norm: np.ndarray, qvec: list[float], k: int) -> list[int]:
    """retrieval.search와 동일한 코사인 top-k (인덱스 반환)."""
    q = np.asarray(qvec, dtype=np.float32)
    q_norm = q / (np.linalg.norm(q) + 1e-8)
    scores = matrix_norm @ q_norm
    return [int(i) for i in np.argsort(scores)[::-1][:k]]


def main() -> int:
    if not FIXTURE.exists():
        print(
            "❌ fixture 없음(eval/rag_fixture.json). "
            "`python eval/build_rag_fixture.py`로 먼저 생성하세요.",
            file=sys.stderr,
        )
        return 2
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    chunks = fx["chunks"]
    qmap = fx["queries"]
    cases = [json.loads(ln) for ln in GOLDEN.read_text(encoding="utf-8").splitlines() if ln.strip()]

    matrix = np.asarray([c["embedding"] for c in chunks], dtype=np.float32)
    matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-8)

    min_pass = float(os.getenv("RAG_EVAL_MIN", DEFAULT_MIN))
    print(f"\n== RAG 검색 eval  (청크 {len(chunks)} · 케이스 {len(cases)} · 기준 {min_pass:.0%}) ==\n")
    print(f"{'id':<20}{'결과':<6}{'키워드':<8}{'문서':<8}top-1 문서")
    print("-" * 72, flush=True)

    passed = 0
    for c in cases:
        qvec = qmap.get(c["id"])
        if qvec is None:
            print(f"{c['id']:<20}{'❌':<5} (fixture에 질문 임베딩 없음 — build 재실행 필요)", flush=True)
            continue
        k = int(c.get("k", 5))
        idx = _topk(matrix_norm, qvec, k)
        top_text = "\n".join(chunks[i]["content"] for i in idx)
        top1_title = chunks[idx[0]]["title"] if idx else ""

        kw_ok = all(kw in top_text for kw in c.get("expect_keywords", []))
        exp_doc = c.get("expect_doc")
        doc_ok = (exp_doc is None) or (top1_title == exp_doc)
        ok = kw_ok and doc_ok
        passed += ok
        print(
            f"{c['id']:<20}{'✅' if ok else '❌':<5} "
            f"{'✓' if kw_ok else '✗':<8}{('—' if exp_doc is None else ('✓' if doc_ok else '✗')):<8}{top1_title}",
            flush=True,
        )

    rate = passed / len(cases) if cases else 0.0
    print("-" * 72)
    status = "PASS" if rate >= min_pass else "FAIL"
    print(f"\n통과율: {passed}/{len(cases)} = {rate:.0%}  (기준 {min_pass:.0%}) → {status}\n")
    return 0 if rate >= min_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
