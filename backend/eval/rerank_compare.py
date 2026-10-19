"""리랭커 전/후 검색 품질 비교 — 커밋된 fixture 위에서 '측정 → 개선 → 재측정'.

같은 골든셋(rag_golden.jsonl)·같은 1차 후보(bge-m3 코사인)를 두고,
  - before: 코사인 top-k
  - after : 코사인 top-RERANK_POOL → cross-encoder 재정렬 top-k
의 통과율(키워드 Hit@k + top-1 문서 정확도)을 나란히 비교한다.

run_rag_eval.py(CI·pre-push 게이트)는 numpy 전용이라 건드리지 않는다. 이 스크립트는
torch(cross-encoder)가 필요하므로 로컬 측정용이다.

실행:
    cd backend && python eval/rerank_compare.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.rerank import rerank  # noqa: E402
from app.rag.retrieval import RERANK_POOL  # noqa: E402

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "rag_fixture.json"
GOLDEN = HERE / "rag_golden.jsonl"


def _kw_hit(case: dict, chunk: dict) -> bool:
    return all(kw in chunk["content"] for kw in case.get("expect_keywords", []))


def _first_rank(case: dict, top_chunks: list[dict]) -> int:
    """키워드를 모두 포함하는 첫 청크의 1-based 순위. 없으면 0(미발견)."""
    for r, c in enumerate(top_chunks, start=1):
        if _kw_hit(case, c):
            return r
    return 0


def _metrics(case: dict, top_chunks: list[dict]) -> dict:
    """세 지표: Hit@k(하나라도 포함) · Top-1(1위가 포함) · RR(역순위)."""
    rank = _first_rank(case, top_chunks)
    return {
        "hit": 1 if rank > 0 else 0,
        "top1": 1 if rank == 1 else 0,
        "rr": (1.0 / rank) if rank > 0 else 0.0,
    }


def main() -> int:
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    chunks = fx["chunks"]
    qmap = fx["queries"]
    cases = [json.loads(ln) for ln in GOLDEN.read_text(encoding="utf-8").splitlines() if ln.strip()]

    matrix = np.asarray([c["embedding"] for c in chunks], dtype=np.float32)
    matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-8)

    print(f"\n== 리랭커 전/후 비교  (청크 {len(chunks)} · 케이스 {len(cases)} · 풀 {RERANK_POOL}) ==\n")
    print(f"{'id':<20}{'top1 b→a':<12}{'rank b→a':<12}변화")
    print("-" * 64, flush=True)

    agg = {"before": {"hit": 0, "top1": 0, "rr": 0.0}, "after": {"hit": 0, "top1": 0, "rr": 0.0}}
    n = 0
    for c in cases:
        qvec = qmap.get(c["id"])
        if qvec is None:
            continue
        n += 1
        k = int(c.get("k", 5))
        q = np.asarray(qvec, dtype=np.float32)
        q_norm = q / (np.linalg.norm(q) + 1e-8)
        order = np.argsort(matrix_norm @ q_norm)[::-1]

        before = [chunks[int(i)] for i in order[:k]]
        pool = [chunks[int(i)] for i in order[:RERANK_POOL]]
        after = rerank(c["question"], pool, k)

        mb, ma = _metrics(c, before), _metrics(c, after)
        for key in agg["before"]:
            agg["before"][key] += mb[key]
            agg["after"][key] += ma[key]

        rb, ra = _first_rank(c, before), _first_rank(c, after)
        mark = "→" if rb == ra else ("↑ 개선" if (ra and (rb == 0 or ra < rb)) else "↓ 저하")
        print(
            f"{c['id']:<20}{str(mb['top1'])+'→'+str(ma['top1']):<12}"
            f"{str(rb)+'→'+str(ra):<12}{mark}",
            flush=True,
        )

    b, a = agg["before"], agg["after"]
    print("-" * 64)
    print("\n지표 (before → after):")
    print(f"  Hit@{int(cases[0].get('k',5))} (포함)   {b['hit']}/{n} → {a['hit']}/{n}")
    print(f"  Top-1 정확도    {b['top1']/n:.0%} → {a['top1']/n:.0%}   (1위가 정답 청크)")
    print(f"  MRR             {b['rr']/n:.3f} → {a['rr']/n:.3f}   (평균 역순위, 높을수록 좋음)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
