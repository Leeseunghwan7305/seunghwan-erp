"""RAG 리랭커 — cross-encoder로 1차(bge-m3 코사인) 후보를 재정렬한다.

2단계 검색: 코사인으로 넓게(top-N) 후보를 뽑고, cross-encoder가 (질의, 본문) 쌍을
직접 보고 정밀하게 재점수화한다. bi-encoder(임베딩 내적)보다 느리지만 정확하다.

torch는 선택적 의존성(requirements-ml.txt)이다. 모델은 lazy 로드하고 미설치면
친절한 에러를 던진다(핵심 앱·CI의 numpy 전용 경로는 영향 없음).
"""
from typing import Any

# 다국어 MS MARCO 리랭커(한국어 포함). 1차 후보를 (질의, 본문) 쌍으로 재점수.
MODEL_NAME = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as e:  # noqa: BLE001
            raise RuntimeError(
                "리랭커 미설치 — `pip install -r backend/requirements-ml.txt` 후 사용하세요."
            ) from e
        _model = CrossEncoder(MODEL_NAME)
    return _model


def _reorder(scores: list[float], candidates: list[dict], top_k: int) -> list[dict]:
    """점수 내림차순으로 후보를 재정렬하고 rerank_score를 붙여 top_k 반환(순수 함수 — 테스트 대상)."""
    ranked = sorted(
        (dict(c, rerank_score=round(float(s), 4)) for c, s in zip(candidates, scores)),
        key=lambda c: c["rerank_score"],
        reverse=True,
    )
    return ranked[:top_k]


def rerank(query: str, candidates: list[dict], top_k: int, text_key: str = "content") -> list[dict]:
    """후보(dict 리스트)를 cross-encoder로 재정렬해 top_k를 반환. 각 항목에 rerank_score 부여."""
    if not candidates:
        return []
    pairs = [[query, c.get(text_key, "")] for c in candidates]
    scores = _get_model().predict(pairs)
    return _reorder([float(s) for s in scores], candidates, top_k)
