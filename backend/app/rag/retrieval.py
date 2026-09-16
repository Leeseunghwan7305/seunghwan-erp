"""임베딩 코사인 top-k 검색. 검색 API와 챗 도구(search_documents)가 공유한다.

프로토타입 규모(수백~수천 청크)를 가정해, ready 문서의 전체 청크를 메모리로 읽어
numpy로 코사인 유사도를 한 번에 계산한다. pgvector 없이 이식성을 유지한다.
"""
import numpy as np
from sqlmodel import Session, select

from ..database import engine
from ..models import DocChunk, Document, DocStatus
from .embeddings import embed_query


def search(query: str, top_k: int = 5) -> list[dict]:
    """query와 가장 유사한 청크 top_k를 반환.

    반환 항목: {document_id, title, ordinal, content, score}
    ready 문서가 없거나 query가 비면 빈 리스트.
    """
    query = (query or "").strip()
    if not query:
        return []

    with Session(engine) as session:
        rows = session.exec(
            select(DocChunk, Document.title)
            .join(Document, Document.id == DocChunk.document_id)
            .where(Document.status == DocStatus.ready)
        ).all()

    chunks = [(chunk, title) for chunk, title in rows if chunk.embedding]
    if not chunks:
        return []

    matrix = np.array([c.embedding for c, _ in chunks], dtype=np.float32)
    q = np.array(embed_query(query), dtype=np.float32)

    # 코사인 유사도 = 정규화된 내적. 0-벡터 방어를 위해 작은 eps를 더한다.
    matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-8)
    q_norm = q / (np.linalg.norm(q) + 1e-8)
    scores = matrix_norm @ q_norm

    top_idx = np.argsort(scores)[::-1][:top_k]
    results = []
    for i in top_idx:
        chunk, title = chunks[int(i)]
        results.append(
            {
                "document_id": chunk.document_id,
                "title": title,
                "ordinal": chunk.ordinal,
                "content": chunk.content,
                "score": round(float(scores[int(i)]), 4),
            }
        )
    return results
