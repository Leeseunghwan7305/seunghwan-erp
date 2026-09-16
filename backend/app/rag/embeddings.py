"""Ollama 임베딩(bge-m3, dim 1024).

Ollama `/api/embed`는 input에 문자열/문자열 리스트를 받아 embeddings를 돌려준다.
Ollama가 꺼져 있거나 모델이 없으면 RuntimeError로 명확히 알린다.
"""
import os

import httpx

EMBED_DIM = 1024


def embed_texts(texts: list[str]) -> list[list[float]]:
    """여러 텍스트를 임베딩한다. 입력 순서와 동일한 순서로 벡터를 반환."""
    if not texts:
        return []

    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")
    try:
        r = httpx.post(
            f"{base}/api/embed",
            json={"model": model, "input": texts},
            timeout=120.0,
        )
        r.raise_for_status()
        data = r.json()
    except httpx.ConnectError as e:
        raise RuntimeError(
            f"Ollama 서버에 연결할 수 없습니다({base}). 'ollama serve'로 실행하세요."
        ) from e
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"임베딩 호출 오류: {e}") from e

    embeddings = data.get("embeddings")
    if not embeddings or len(embeddings) != len(texts):
        raise RuntimeError(
            f"임베딩 응답이 올바르지 않습니다(모델 '{model}'). 'ollama pull {model}' 확인."
        )
    return embeddings


def embed_query(text: str) -> list[float]:
    """단일 쿼리 임베딩."""
    return embed_texts([text])[0]
