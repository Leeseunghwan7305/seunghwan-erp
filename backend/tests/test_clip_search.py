"""CLIP 이미지 검색의 순수 로직(cosine_topk) 유닛테스트.

실제 CLIP 모델(torch)은 무거워 CI에서 돌리지 않는다. 검색의 코어인 코사인 랭킹은
모델과 무관한 순수 numpy 함수라 여기서 고정한다(정렬·정규화·top-k 경계).
"""
from app.rag.clip_search import cosine_topk


def test_ranks_by_cosine_similarity():
    matrix = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    # query가 [1,0]과 완전 일치 → 0번이 1위
    hits = cosine_topk([1.0, 0.0], matrix, k=3)
    assert hits[0][0] == 0
    assert abs(hits[0][1] - 1.0) < 1e-5


def test_magnitude_invariant():
    # 방향이 같고 크기만 다른 벡터는 같은 유사도(정규화 내적)
    hits = cosine_topk([2.0, 0.0], [[10.0, 0.0]], k=1)
    assert abs(hits[0][1] - 1.0) < 1e-5


def test_topk_limits_results():
    matrix = [[1.0, 0.0]] * 5
    assert len(cosine_topk([1.0, 0.0], matrix, k=2)) == 2


def test_empty_matrix_returns_empty():
    assert cosine_topk([1.0, 0.0], [], k=5) == []


def test_order_is_descending():
    matrix = [[0.1, 0.0], [1.0, 0.0], [0.5, 0.0]]
    scores = [s for _, s in cosine_topk([1.0, 0.0], matrix, k=3)]
    assert scores == sorted(scores, reverse=True)
