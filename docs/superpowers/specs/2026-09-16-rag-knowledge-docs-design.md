# RAG 지식 문서 관리 (AI 카테고리) — 설계

- 날짜: 2026-09-16
- 상태: 승인됨 (구현 대기)
- 관련: `docs/ai-chatbot-plan.md`, 메모리 `erp-ai-chatbot`, `erp-design-system`, `erp-local-dev-env`

## 목표

AI 어시스턴트가 답변에 쓸 수 있는 **사내 지식 문서**를 업로드·색인·검색·삭제하는
관리 페이지를 "AI" 카테고리에 만든다. 업로드된 문서는 임베딩 검색(RAG)으로
챗봇 도구에 연결되어, 재고/주문 등 구조화 데이터 도구와 함께 사용된다.

프로토타입(v0.1) 수준: 인증/멀티유저/권한 없음, 문서 수는 수백~수천 청크 규모 가정.

## 결정 사항 (확정)

- **범위**: 관리 페이지 + 챗 연동 (검색을 챗봇 도구로 노출).
- **벡터 저장/검색**: Postgres 일반 컬럼(JSON `list[float]`) + Python(numpy) 브루트포스 코사인.
  pgvector·전용 벡터DB 미도입 — 이식성 유지, 신규 인프라 0.
- **문서 입력**: 텍스트 붙여넣기 + 파일 업로드(.txt / .md / .pdf). PDF는 pypdf로 추출.
- **임베딩**: Ollama `bge-m3` (`/api/embed`, dim 1024). 이미 설치·검증됨.
- **인제스트**: 비동기(FastAPI BackgroundTask) + 프론트 상태 폴링.
- **청크**: 문단 경계 우선, 약 800자 / 100자 오버랩. 검색 top_k 기본 5.

## 아키텍처

### 1. 사이드바 / 라우팅 (`frontend/app/components/Sidebar.tsx`)

`groups`에 "AI" 카테고리 신설:
- `AI 어시스턴트` (`/chat`) — 기존 "메인"에서 이동
- `지식 문서` (`/ai/documents`) — 신설

"메인"에는 `대시보드`만 남긴다.

### 2. 데이터 모델 (`backend/app/models.py`에 추가)

```
Document
  id, title, source_type: "paste"|"txt"|"md"|"pdf", filename: str|None,
  char_count: int, chunk_count: int,
  status: "indexing"|"ready"|"error", error: str|None,
  created_at: datetime

DocChunk
  id, document_id: FK(document.id, cascade delete), ordinal: int,
  content: str, embedding: list[float]  # JSON 컬럼, dim 1024
```

임베딩은 `sa_column`으로 JSON 타입 지정. RAG 모델을 `models.py`에 두어
`SQLModel.metadata` 등록을 보장(기존 컨벤션과 일치).

### 3. 백엔드 RAG 모듈 (`backend/app/rag/`)

- `extract.py` — `extract_text(filename, data: bytes) -> str`.
  txt/md는 UTF-8 디코드(실패 시 관대한 디코드), pdf는 pypdf 페이지별 텍스트 결합.
- `chunk.py` — `chunk_text(text) -> list[str]`. 문단(빈 줄) 경계로 모으다가
  ~800자 초과 시 분할, 인접 청크 간 100자 오버랩.
- `embeddings.py` — `embed_texts(texts: list[str]) -> list[list[float]]`.
  Ollama `/api/embed`(model=`OLLAMA_EMBED_MODEL`, 기본 bge-m3) 호출.
  Ollama 미가동 시 `RuntimeError`로 명확한 메시지.
- `retrieval.py` — `search(query: str, top_k=5) -> list[dict]`.
  쿼리 임베딩 후 전체 `DocChunk`(ready 문서만) 대상 numpy 코사인 유사도 top_k.
  반환: `{document_id, title, ordinal, content, score}`. **검색 API와 챗 도구가 공유.**
- `router.py` — `APIRouter(prefix="/rag")`:
  - `POST /rag/documents` — multipart(`file`, `title`) 또는 JSON(`title`, `text`).
    Document(status=indexing) 저장 후 BackgroundTask로
    추출→청크→임베딩→DocChunk 저장→status=ready(실패 시 error+메시지).
  - `GET /rag/documents` — 목록(상태·카운트·등록일).
  - `DELETE /rag/documents/{id}` — 문서+청크 삭제.
  - `POST /rag/search` — `{query, top_k?}` → 상위 청크(점수·출처).

`main.py`에 `rag_router` include.

### 4. 챗 연동 (`backend/app/chat/`)

- `tools.py`: `TOOL_DEFS`에 `search_documents` 추가
  (`{query: string}`, "업로드된 사내 지식 문서에서 관련 내용을 검색한다").
  `execute_tool`에서 `rag.retrieval.search` 호출, 청크 텍스트+출처 반환.
  → provider-중립 구조라 claude/local 양쪽 자동 노출.
- `providers.py`: `SYSTEM_PROMPT`에 사내 문서 검색 가능 안내 한 줄 추가.
- `frontend/app/chat/page.tsx`: `TOOL_LABEL`에 `search_documents: "문서 검색"` 추가.

### 5. 프론트 관리 페이지 (`frontend/app/ai/documents/page.tsx`)

- 문서 추가 카드: 탭(텍스트 붙여넣기 / 파일 업로드) + 제목 입력 + 등록 버튼.
- 문서 목록 테이블: 제목·형식·청크수·글자수·상태 배지·등록일·삭제.
  `indexing` 문서가 있으면 3초 간격 폴링, 모두 ready/error면 폴링 중단.
- 검색 테스트 패널: 쿼리 입력 → top-k 청크(점수 + 출처 문서명).
- 디자인: 웨어하우스 원장 팔레트, 숫자는 mono(`.num`), 기존 `PageHeader`/`Badge`/`DataTable` 재사용.

### 6. 의존성 / 설정 / API 클라이언트

- `backend/requirements.txt`: `pypdf`, `numpy` 추가.
- `.env` / `.env.example`: `OLLAMA_EMBED_MODEL=bge-m3` 추가.
- `frontend/app/lib/api.ts`: `RagDocument` 타입, `ragDocuments()`/`createRagDocument()`/
  `deleteRagDocument()`/`ragSearch()` 추가.

## 데이터 흐름

업로드 → `POST /rag/documents`(status=indexing 즉시 반환) → BackgroundTask:
추출→청크→bge-m3 임베딩→DocChunk 저장→status=ready. 프론트는 목록 폴링으로 상태 갱신.

검색(테스트 패널 또는 챗 도구) → `retrieval.search`: 쿼리 임베딩 → 전 청크 코사인 top_k → 결과.

## 오류 처리

- Ollama 미가동: 인제스트는 status=error+메시지, 검색은 명확한 오류 반환.
- PDF 파싱 실패/빈 텍스트: status=error.
- 삭제/검색 대상 없음: 404 / 빈 결과.
- 프로토타입: 상세 오류를 그대로 노출(운영 전 정제).

## 테스트

- 백엔드: chunk(경계·오버랩), retrieval 코사인 순위(임베딩 목킹), 라우터 CRUD(테스트 DB).
- 수동 E2E: 문서 업로드→ready→검색 테스트→챗에서 "문서 검색" 도구 호출 확인.

## Non-goals

자동 재인덱싱, 대용량 스트리밍 파싱, 권한/네임스페이스, 하이브리드(BM25) 검색, 인증.
