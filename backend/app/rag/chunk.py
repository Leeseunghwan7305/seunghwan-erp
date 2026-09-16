"""텍스트 청킹: 문단 경계를 우선하되 최대 길이를 넘기면 분할, 인접 청크 간 오버랩.

RAG 검색 품질은 청크 경계에 민감하다. 문단(빈 줄) 단위로 모으다가 목표 길이를
넘으면 끊고, 다음 청크 앞부분에 이전 청크 끝 일부를 겹쳐(overlap) 문맥 단절을 줄인다.
"""

CHUNK_SIZE = 800      # 목표 청크 길이(문자)
CHUNK_OVERLAP = 100   # 인접 청크 간 겹침(문자)


def _split_long(paragraph: str, size: int) -> list[str]:
    """단일 문단이 size보다 길면 size 단위로 강제 분할."""
    return [paragraph[i : i + size] for i in range(0, len(paragraph), size)]


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """text를 청크 리스트로 나눈다. 빈 입력이면 빈 리스트."""
    text = (text or "").strip()
    if not text:
        return []

    # 문단(빈 줄) 단위로 1차 분할. 너무 긴 문단은 강제로 쪼갠다.
    paragraphs: list[str] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if len(block) > size:
            paragraphs.extend(_split_long(block, size))
        else:
            paragraphs.append(block)

    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if not current:
            current = para
        elif len(current) + 2 + len(para) <= size:
            current = f"{current}\n\n{para}"
        else:
            chunks.append(current)
            # 오버랩: 이전 청크 끝 overlap 문자를 다음 청크 앞에 붙인다.
            tail = current[-overlap:] if overlap else ""
            current = f"{tail}\n\n{para}" if tail else para
    if current:
        chunks.append(current)
    return chunks
