"""리랭커 재정렬 로직(_reorder) 유닛테스트 — cross-encoder 점수를 받아 순서를 뒤집는
순수 함수만 검증한다(torch·모델 불필요). 모델 추론은 로컬 rerank_compare.py로 측정.
"""
from app.rag.rerank import _reorder


def _cands(n):
    return [{"content": f"doc{i}", "id": i} for i in range(n)]


def test_reorders_by_score_desc():
    cands = _cands(3)
    # 1차 순서(0,1,2)와 무관하게 cross-encoder 점수로 재정렬
    out = _reorder([0.1, 0.9, 0.5], cands, top_k=3)
    assert [c["id"] for c in out] == [1, 2, 0]


def test_truncates_to_top_k():
    out = _reorder([0.1, 0.2, 0.3, 0.4], _cands(4), top_k=2)
    assert len(out) == 2
    assert [c["id"] for c in out] == [3, 2]


def test_attaches_rerank_score():
    out = _reorder([0.42], [{"content": "x"}], top_k=1)
    assert out[0]["rerank_score"] == 0.42


def test_preserves_original_fields():
    out = _reorder([0.5], [{"content": "x", "title": "doc-A", "score": 0.3}], top_k=1)
    assert out[0]["title"] == "doc-A"
    assert out[0]["score"] == 0.3  # 1차 코사인 점수도 보존


def test_empty_candidates_via_rerank():
    from app.rag.rerank import rerank

    assert rerank("q", [], top_k=5) == []
