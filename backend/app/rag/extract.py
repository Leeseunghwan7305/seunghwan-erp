"""업로드 파일 → 텍스트 추출.

- txt / md: UTF-8 우선, 실패 시 관대한 디코드(cp949 → latin-1 순).
- pdf: pypdf로 페이지별 텍스트 추출 후 결합.
확장자로 source_type을 판별한다.
"""
import io

from ..models import DocSourceType


def detect_source_type(filename: str) -> DocSourceType:
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        return DocSourceType.pdf
    if lower.endswith(".md") or lower.endswith(".markdown"):
        return DocSourceType.md
    return DocSourceType.txt


def _decode(data: bytes) -> str:
    for enc in ("utf-8", "cp949", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:  # pragma: no cover - 의존성 미설치 방어
        raise RuntimeError("pypdf가 설치되지 않았습니다. requirements를 설치하세요.") from e

    reader = PdfReader(io.BytesIO(data))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(p for p in pages if p)


def extract_text(filename: str, data: bytes) -> str:
    """파일명·바이트에서 텍스트를 추출한다. 빈 결과면 호출측이 오류 처리."""
    source_type = detect_source_type(filename)
    if source_type == DocSourceType.pdf:
        return _extract_pdf(data)
    return _decode(data)
