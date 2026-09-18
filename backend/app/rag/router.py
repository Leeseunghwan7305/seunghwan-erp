"""RAG 지식 문서 API: 업로드(비동기 인제스트)·목록·삭제·검색."""
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


# 매뉴얼 전문 조립 시 최적 청크 기준 앞뒤로 이어붙일 청크 수(연속 섹션 재구성용).
# 매칭 청크에 대개 섹션 머리말이 있어 그 지점부터 이어 붙이는 게 가장 자연스럽다.
_MANUAL_BEFORE = 0
_MANUAL_AFTER = 2


@router.post("/manual")
def manual(req: ManualRequest):
    """화면별 매뉴얼 전문: 질의에 가장 잘 맞는 섹션을 인접 청크까지 이어 재구성해 반환.

    단일 스니펫이 아니라 최적 청크 앞뒤 청크를 ordinal 순서로 이어 붙여(오버랩 제거)
    '읽기용 매뉴얼 본문'으로 돌려준다. HelpDrawer의 매뉴얼 탭에서 사용.
    """
    hits = search(req.query, top_k=6)
    if not hits:
        return {"title": None, "text": "", "score": 0.0}
    best = hits[0]
    center = best["ordinal"]
    lo, hi = max(0, center - _MANUAL_BEFORE), center + _MANUAL_AFTER
    with Session(engine) as session:
        chunks = session.exec(
            select(DocChunk)
            .where(DocChunk.document_id == best["document_id"])
            .where(DocChunk.ordinal >= lo)
            .where(DocChunk.ordinal <= hi)
            .order_by(DocChunk.ordinal)
        ).all()
    return {
        "title": best["title"],
        "text": _join_chunks([c.content for c in chunks]),
        "score": best["score"],
    }
