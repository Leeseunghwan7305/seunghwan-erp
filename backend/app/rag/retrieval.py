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


# 자동 주입 임계값. bge-m3 임베딩에서는 한국어·도메인 어휘가 겹쳐 '무관한 질문'도
# 단일 지식문서와 ~0.44의 잡음 유사도가 나온다(예: '비트코인 시세' 0.475). 반면 실제
# 관련 질문은 0.52~0.66에 몰린다. 그 사이 골(0.50)에 임계값을 둬, 웹검색으로 답할 질문에
# 사내 문서가 잘못 주입돼 가짜 '(출처: 사내 문서)'가 붙는 것을 막는다.
CONTEXT_MIN_SCORE = 0.50


def context_for(query: str, top_k: int = 4, min_score: float = CONTEXT_MIN_SCORE) -> str:
    """query로 문서를 미리 검색해 시스템 프롬프트에 붙일 '참고 문서' 블록을 만든다.

    모델이 search_documents 호출을 스스로 판단하지 못해도 근거가 항상 컨텍스트에
    들어가도록 하는 용도. 관련 청크가 없으면 빈 문자열을 반환한다.
    """
    if not (query or "").strip():
        return ""
    try:
        hits = [h for h in search(query, top_k=top_k) if h["score"] >= min_score]
    except Exception:  # noqa: BLE001 - 검색 실패가 대화를 막지 않도록
        return ""
    if not hits:
        return ""
    blocks = "\n\n".join(f"[출처: {h['title']}]\n{h['content']}" for h in hits)
    return (
        "\n\n# 참고 문서(사내 지식 자동 검색 결과)\n"
        "아래는 사용자의 현재 질문으로 사내 문서를 미리 검색한 결과다. "
        "질문과 관련된 내용이 있으면 반드시 이 내용을 근거로 답하라. "
        "(별도로 search_documents 도구를 다시 부를 필요는 없다.)\n"
        "이 문서 내용을 근거로 답한 경우, 답변 맨 끝에 줄을 바꿔 '(출처: 문서제목)' 형식으로 "
        "실제로 사용한 문서 제목을 밝혀라.\n\n"
        f"{blocks}\n"
    )
