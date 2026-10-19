"""RAG eval용 임베딩 fixture 생성기 (로컬 전용 — Ollama + DB 필요).

왜 fixture인가:
    실시간 검색 eval은 임베딩(Ollama bge-m3)과 Postgres가 있어야 돈다 → CI에서 무겁다.
    여기서 '코퍼스 청크 임베딩'과 '골든 질문 임베딩'을 미리 계산해 JSON으로 커밋해두면,
    run_rag_eval.py는 외부 서비스 없이 순수 numpy 코사인 계산만으로 검색을 재현한다.
    → CI·pre-push 훅에서 빠르고 결정적으로 검색 회귀를 잡는다.

언제 다시 돌리나:
    지식 코퍼스(문서)나 임베딩 모델을 바꿨을 때. 그 외에는 커밋된 fixture를 그대로 쓴다.

실행:
    cd backend && ../.venv/bin/python eval/build_rag_fixture.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session, select  # noqa: E402

from app.database import engine  # noqa: E402
from app.models import DocChunk, Document, DocStatus  # noqa: E402
from app.rag.embeddings import embed_texts  # noqa: E402

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "rag_golden.jsonl"
FIXTURE = HERE / "rag_fixture.json"
_ROUND = 6  # 임베딩 소수 자리(파일 크기 ↓, 랭킹에는 영향 없음)


def _round(vec: list[float]) -> list[float]:
    return [round(float(x), _ROUND) for x in vec]


def main() -> int:
    cases = [json.loads(ln) for ln in GOLDEN.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not cases:
        print("golden 비어있음", file=sys.stderr)
        return 1

    # 1) 코퍼스: ready 문서의 모든 청크(= retrieval.search가 보는 것과 동일)
    with Session(engine) as s:
        rows = s.exec(
            select(DocChunk, Document.title)
            .join(Document, Document.id == DocChunk.document_id)
            .where(Document.status == DocStatus.ready)
        ).all()
    chunks = [
        {"title": title, "content": c.content, "embedding": _round(c.embedding)}
        for c, title in rows
        if c.embedding
    ]
    if not chunks:
        print("ready 청크 없음 — 문서를 먼저 인제스트하세요", file=sys.stderr)
        return 1

    # 2) 골든 질문 임베딩(검색 로직과 동일한 모델로)
    q_vecs = embed_texts([c["question"] for c in cases])
    queries = {c["id"]: _round(v) for c, v in zip(cases, q_vecs)}

    FIXTURE.write_text(
        json.dumps(
            {
                "model": "bge-m3",
                "note": "run_rag_eval용 고정 임베딩. 코퍼스/모델 변경 시 build_rag_fixture.py 재실행.",
                "n_chunks": len(chunks),
                "n_queries": len(queries),
                "chunks": chunks,
                "queries": queries,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    kb = FIXTURE.stat().st_size / 1024
    print(f"fixture 생성: {FIXTURE.name}  (청크 {len(chunks)} · 질문 {len(queries)} · {kb:.0f}KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
