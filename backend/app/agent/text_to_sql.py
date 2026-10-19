"""Text-to-SQL — 자연어 질문을 읽기전용 SELECT로 바꿔 ERP DB에 묻는다.

안전 설계(3겹 방어):
  1) 프롬프트: 스키마 안에서 SELECT 한 문장만 쓰도록 유도(약한 보장).
  2) 가드(guard_sql): denylist·단일문·LIMIT 강제 — 코드 레벨 검증(이 함수가 계약).
  3) 실행: postgresql_readonly=True 트랜잭션 + statement_timeout — DB 레벨에서
     쓰기·장기쿼리를 원천 차단(LLM이 뚫려도 DB가 거부).

생성된 SQL을 그대로 공개(투명성)하고, 결과는 컬럼+행으로 돌려준다(표 렌더용).
"""
import json
import os
import re
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Iterator

import httpx
from sqlalchemy import text
from sqlmodel import SQLModel

from .. import models  # noqa: F401  SQLModel.metadata에 테이블 등록
from ..database import engine

DEFAULT_LIMIT = 100
STMT_TIMEOUT_MS = 5000

# 쓰기·DDL·위험 구문 denylist(단어 경계로 매칭). SELECT/WITH만 통과시키므로
# 사실상 중복 방어지만, 서브쿼리에 숨긴 구문까지 잡는다.
_DENY = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|"
    r"copy|merge|call|do|vacuum|analyze|reindex|cluster|lock|"
    r"for\s+update|for\s+share)\b",
    re.IGNORECASE,
)
_STARTS_OK = re.compile(r"^\s*(with|select)\b", re.IGNORECASE)
_HAS_LIMIT = re.compile(r"\blimit\b", re.IGNORECASE)
_FENCE = re.compile(r"```(?:sql)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


def build_schema() -> str:
    """SQLModel 메타데이터에서 테이블·컬럼·타입을 뽑아 프롬프트용 스키마 문자열을 만든다."""
    lines: list[str] = []
    for table in SQLModel.metadata.sorted_tables:
        cols = ", ".join(f"{c.name} {c.type}" for c in table.columns)
        # order 등 예약어 테이블은 모델이 큰따옴표로 감싸도록 표기
        tname = f'"{table.name}"' if table.name in {"order"} else table.name
        lines.append(f"- {tname}({cols})")
    return "\n".join(lines)


def guard_sql(raw: str) -> tuple[bool, str]:
    """생성된 SQL을 검증·정리한다. 반환: (통과여부, 정리된_SQL 또는 차단사유).

    - 마크다운 펜스 제거, 앞뒤 공백·세미콜론 정리
    - SELECT/WITH로 시작하는 단일문만 허용
    - denylist(쓰기·DDL), 주석(-- /*), 다중문(;) 차단
    - LIMIT 없으면 자동 부착
    """
    if not raw or not raw.strip():
        return False, "빈 SQL"
    sql = raw.strip()
    m = _FENCE.search(sql)
    if m:
        sql = m.group(1).strip()
    sql = sql.rstrip(";").strip()  # 끝 세미콜론 1개 허용(정리)

    if ";" in sql:
        return False, "다중 문장(;)은 허용되지 않습니다"
    if "--" in sql or "/*" in sql:
        return False, "주석은 허용되지 않습니다"
    if not _STARTS_OK.match(sql):
        return False, "SELECT 문만 허용됩니다"
    deny = _DENY.search(sql)
    if deny:
        return False, f"허용되지 않는 구문: {deny.group(0).upper()}"

    if not _HAS_LIMIT.search(sql):
        sql = f"{sql}\nLIMIT {DEFAULT_LIMIT}"
    return True, sql


def _jsonable(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, Enum):
        return v.value
    return v


def _execute(sql: str) -> dict[str, Any]:
    """읽기전용 트랜잭션 + statement_timeout로 실행하고 컬럼·행을 돌려준다."""
    with engine.connect().execution_options(postgresql_readonly=True) as conn:
        conn.execute(text(f"SET statement_timeout = {STMT_TIMEOUT_MS}"))
        result = conn.execute(text(sql))
        columns = list(result.keys())
        rows = [[_jsonable(v) for v in row] for row in result.fetchall()]
    return {"columns": columns, "rows": rows}


_SYSTEM = """너는 PostgreSQL 전문가다. 아래 스키마만 사용해 사용자 질문에 답하는 SQL 한 문장을 작성한다.

규칙:
- 반드시 SELECT 문 하나만. 설명·주석·마크다운 없이 SQL만 출력한다.
- 스키마에 있는 테이블/컬럼만 사용한다.
- 예약어와 겹치는 테이블명(order)은 반드시 큰따옴표로 감싼다: "order".
- 집계·조인은 자유롭게. 결과가 많을 수 있으면 LIMIT을 붙인다.
- PostgreSQL 문법. 날짜는 current_date, date_trunc('month', ...) 등을 쓴다.

스키마:
{schema}"""


def _generate_sql(question: str, model: str) -> Iterator[dict]:
    """Ollama로 SQL을 생성하며 토큰을 sql 델타로 흘린다. 누적본은 done에 담는다."""
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ol_model = model if (model.startswith("qwen") or ":" in model) else os.getenv("OLLAMA_MODEL", "qwen2.5")
    system = _SYSTEM.format(schema=build_schema())
    parts: list[str] = []
    try:
        with httpx.stream(
            "POST",
            f"{base}/api/chat",
            json={
                "model": ol_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": question},
                ],
                "stream": True,
                "options": {"temperature": 0},
            },
            timeout=120.0,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                d = (obj.get("message", {}) or {}).get("content") or ""
                if d:
                    parts.append(d)
                    yield {"type": "sql_delta", "content": d}
                if obj.get("done"):
                    break
    except httpx.ConnectError:
        yield {"type": "error", "content": f"Ollama 서버에 연결할 수 없습니다({base})."}
        return
    except Exception as e:  # noqa: BLE001
        yield {"type": "error", "content": f"SQL 생성 오류: {e}"}
        return
    yield {"type": "_raw", "content": "".join(parts)}


def run_text_to_sql(question: str, model: str = "local") -> Iterator[dict[str, Any]]:
    """자연어 → SQL 생성(스트리밍) → 가드 → 읽기전용 실행 → 결과. SSE 이벤트 생성기."""
    yield {"type": "schema", "tables": [t.name for t in SQLModel.metadata.sorted_tables]}

    raw = ""
    for evt in _generate_sql(question, model):
        if evt["type"] == "_raw":
            raw = evt["content"]
        elif evt["type"] == "error":
            yield evt
            return
        else:
            yield evt  # sql_delta

    ok, result = guard_sql(raw)
    if not ok:
        yield {"type": "guard", "ok": False, "reason": result}
        yield {"type": "done"}
        return
    cleaned = result
    yield {"type": "guard", "ok": True, "sql": cleaned}

    try:
        data = _execute(cleaned)
    except Exception as e:  # noqa: BLE001
        msg = str(e).split("\n")[0][:300]
        yield {"type": "error", "content": f"실행 오류: {msg}"}
        return
    yield {"type": "rows", "columns": data["columns"], "rows": data["rows"], "count": len(data["rows"])}
    yield {"type": "done"}
