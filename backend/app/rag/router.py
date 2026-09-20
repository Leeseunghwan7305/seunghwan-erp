"""RAG 지식 문서 API: 업로드(비동기 인제스트)·목록·삭제·검색."""
import re
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from sqlmodel import Session, SQLModel, select

from ..database import engine
from ..models import DocChunk, Document, DocSourceType, DocStatus
from .chunk import chunk_text
from .embeddings import embed_texts
from .extract import detect_source_type, extract_text
from .retrieval import search

router = APIRouter(prefix="/rag", tags=["rag"])


# ---- 응답/요청 스키마 -----------------------------------------------------

class DocumentRead(SQLModel):
    id: int
    title: str
    source_type: DocSourceType
    filename: Optional[str]
    char_count: int
    chunk_count: int
    status: DocStatus
    error: Optional[str]
    created_at: str


class SearchRequest(SQLModel):
    query: str
    top_k: int = 5


class ManualRequest(SQLModel):
    query: str
    section: Optional[str] = None  # 예: "4.4" — 주면 그 섹션만 정확히 잘라 반환


def _to_read(doc: Document) -> DocumentRead:
    return DocumentRead(
        id=doc.id,
        title=doc.title,
        source_type=doc.source_type,
        filename=doc.filename,
        char_count=doc.char_count,
        chunk_count=doc.chunk_count,
        status=doc.status,
        error=doc.error,
        created_at=doc.created_at.isoformat(),
    )


# ---- 인제스트(백그라운드) -------------------------------------------------

def _ingest(document_id: int, filename: Optional[str], data: Optional[bytes], text: Optional[str]) -> None:
    """추출→청크→임베딩→저장. status를 ready/error로 전환한다."""
    with Session(engine) as session:
        doc = session.get(Document, document_id)
        if not doc:
            return
        try:
            content = text if text is not None else extract_text(filename or "", data or b"")
            content = (content or "").strip()
            if not content:
                raise RuntimeError("추출된 텍스트가 비어 있습니다.")

            chunks = chunk_text(content)
            if not chunks:
                raise RuntimeError("생성된 청크가 없습니다.")

            embeddings = embed_texts(chunks)
            for ordinal, (chunk, vec) in enumerate(zip(chunks, embeddings)):
                session.add(
                    DocChunk(
                        document_id=doc.id,
                        ordinal=ordinal,
                        content=chunk,
                        embedding=vec,
                    )
                )
            doc.char_count = len(content)
            doc.chunk_count = len(chunks)
            doc.status = DocStatus.ready
            doc.error = None
        except Exception as e:  # noqa: BLE001 - 프로토타입: 오류 메시지를 상태로 노출
            doc.status = DocStatus.error
            doc.error = str(e)
        session.add(doc)
        session.commit()


# ---- 엔드포인트 -----------------------------------------------------------

@router.post("/documents", response_model=DocumentRead, status_code=201)
async def create_document(
    background: BackgroundTasks,
    title: str = Form(...),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """텍스트(text) 또는 파일(file) 중 하나로 문서를 등록하고 비동기 인제스트를 시작한다."""
    title = (title or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="제목을 입력하세요.")

    has_text = bool(text and text.strip())
    has_file = file is not None and bool(file.filename)
    if has_text == has_file:  # 둘 다이거나 둘 다 아님
        raise HTTPException(status_code=422, detail="텍스트 또는 파일 중 하나만 제공하세요.")

    if has_file:
        data = await file.read()
        if not data:
            raise HTTPException(status_code=422, detail="빈 파일입니다.")
        source_type = detect_source_type(file.filename)
        filename = file.filename
        pasted = None
    else:
        data = None
        source_type = DocSourceType.paste
        filename = None
        pasted = text

    with Session(engine) as session:
        doc = Document(title=title, source_type=source_type, filename=filename)
        session.add(doc)
        session.commit()
        session.refresh(doc)
        read = _to_read(doc)

    background.add_task(_ingest, read.id, filename, data, pasted)
    return read


@router.get("/documents", response_model=list[DocumentRead])
def list_documents():
    with Session(engine) as session:
        docs = session.exec(select(Document).order_by(Document.id.desc())).all()
        return [_to_read(d) for d in docs]


def _join_chunks(parts: list[str]) -> str:
    """청크를 순서대로 잇되, 인접 청크 간 오버랩(겹친 텍스트)을 제거해 원문처럼 재구성한다."""
    acc = ""
    for part in parts:
        if not acc:
            acc = part
            continue
        max_l = min(len(acc), len(part))
        overlap = next((l for l in range(max_l, 0, -1) if acc[-l:] == part[:l]), 0)
        acc += part[overlap:]
    return acc


@router.get("/documents/{document_id}/content")
def get_document_content(document_id: int):
    """문서의 저장된 청크를 순서대로 이어 붙여 전체 내용을 반환한다(웹 열람용)."""
    with Session(engine) as session:
        doc = session.get(Document, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
        chunks = session.exec(
            select(DocChunk)
            .where(DocChunk.document_id == document_id)
            .order_by(DocChunk.ordinal)
        ).all()
    return {
        "id": doc.id,
        "title": doc.title,
        "chunk_count": doc.chunk_count,
        "content": _join_chunks([c.content for c in chunks]),
    }


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: int):
    with Session(engine) as session:
        doc = session.get(Document, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
        session.delete(doc)  # cascade로 청크도 삭제
        session.commit()


@router.post("/search")
def search_documents(req: SearchRequest):
    """유사 청크 top_k 조회(관리 페이지 검색 테스트 · 내부 재사용)."""
    return {"results": search(req.query, req.top_k)}


# section 미지정 시(자유 조회) 최적 청크 앞뒤로 이어붙일 청크 수.
_MANUAL_BEFORE = 0
_MANUAL_AFTER = 2


def _clean_manual(text: str) -> str:
    """PDF 추출 잔재(페이지 번호·반복 머리말)를 걷어내 읽기 좋게 정리한다."""
    text = re.sub(r"\n?- \d+ -\n?", "\n", text)
    text = re.sub(r"\n?seunghwan-erp · 사내 운영 지식 문서\n?", "\n", text)
    text = re.sub(r"\n?RAG 내부 문서 · 기준일 [0-9-]+\n?", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _slice_section(full: str, section: str) -> Optional[str]:
    """전체 문서 텍스트에서 'N.N' 섹션 머리말부터 다음 'N.N' 머리말 직전까지 잘라낸다."""
    m = re.search(rf"{re.escape(section)} [가-힣]", full)
    if not m:
        return None
    start = m.start()
    nxt = re.search(r"\n?\d\.\d+ [가-힣]", full[start + 3:])
    end = start + 3 + nxt.start() if nxt else len(full)
    return full[start:end].strip()


@router.post("/manual")
def manual(req: ManualRequest):
    """화면별 매뉴얼 전문.

    section이 주어지면: 임베딩으로 문서를 특정한 뒤 그 문서 전체를 이어 붙여
    해당 섹션(N.N)만 정확히 잘라 반환한다(임베딩 착지 정밀도에 의존하지 않음).
    section이 없으면: 자유 조회로 최적 청크 주변을 이어 붙여 반환한다.
    HelpDrawer의 매뉴얼 탭에서 사용.
    """
    hits = search(req.query, top_k=6)
    if not hits:
        return {"title": None, "text": "", "score": 0.0}
    best = hits[0]

    with Session(engine) as session:
        if req.section:
            # 문서 전체를 순서대로 이어 붙여 섹션을 정확히 슬라이스.
            all_chunks = session.exec(
                select(DocChunk)
                .where(DocChunk.document_id == best["document_id"])
                .order_by(DocChunk.ordinal)
            ).all()
            sliced = _slice_section(_join_chunks([c.content for c in all_chunks]), req.section)
            if sliced:
                return {"title": best["title"], "text": _clean_manual(sliced), "score": best["score"]}

        # 폴백: 최적 청크 주변 창.
        center = best["ordinal"]
        chunks = session.exec(
            select(DocChunk)
            .where(DocChunk.document_id == best["document_id"])
            .where(DocChunk.ordinal >= max(0, center - _MANUAL_BEFORE))
            .where(DocChunk.ordinal <= center + _MANUAL_AFTER)
            .order_by(DocChunk.ordinal)
        ).all()
    return {
        "title": best["title"],
        "text": _clean_manual(_join_chunks([c.content for c in chunks])),
        "score": best["score"],
    }
