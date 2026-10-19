"""Text-to-SQL 안전 가드 유닛테스트 (DB·Ollama 불필요 — 순수 로직).

guard_sql이 이 기능의 '안전 계약'이다: SELECT만 통과, 쓰기·DDL·다중문·주석 차단,
LIMIT 자동 부착. 가드가 뚫리면 임의 SQL이 실행되므로 회귀를 여기서 고정한다.
"""
from app.agent.text_to_sql import DEFAULT_LIMIT, build_schema, guard_sql


def test_plain_select_passes_and_gets_limit():
    ok, sql = guard_sql("SELECT id, name FROM item")
    assert ok
    assert "LIMIT" in sql.upper()


def test_existing_limit_not_duplicated():
    ok, sql = guard_sql("select id from item limit 5")
    assert ok
    assert sql.upper().count("LIMIT") == 1


def test_markdown_fence_stripped():
    ok, sql = guard_sql("```sql\nSELECT * FROM item\n```")
    assert ok
    assert sql.upper().startswith("SELECT")
    assert "`" not in sql


def test_trailing_semicolon_ok():
    ok, sql = guard_sql("SELECT 1 FROM item;")
    assert ok
    assert ";" not in sql


def test_with_cte_passes():
    ok, _ = guard_sql("WITH t AS (SELECT 1 AS n FROM item) SELECT n FROM t LIMIT 1")
    assert ok


def test_insert_blocked():
    ok, reason = guard_sql("INSERT INTO item (name) VALUES ('x')")
    assert not ok


def test_update_blocked():
    ok, _ = guard_sql("UPDATE item SET name = 'x'")
    assert not ok


def test_multi_statement_blocked():
    ok, reason = guard_sql("SELECT 1 FROM item; DROP TABLE item")
    assert not ok


def test_drop_in_subquery_blocked():
    ok, _ = guard_sql("SELECT * FROM item WHERE id IN (SELECT 1); DROP TABLE item")
    assert not ok


def test_comment_blocked():
    ok, _ = guard_sql("SELECT * FROM item -- sneaky")
    assert not ok


def test_for_update_blocked():
    ok, _ = guard_sql("SELECT * FROM item FOR UPDATE")
    assert not ok


def test_empty_blocked():
    ok, _ = guard_sql("   ")
    assert not ok


def test_non_select_blocked():
    ok, _ = guard_sql("TRUNCATE item")
    assert not ok


def test_default_limit_value():
    _, sql = guard_sql("SELECT 1 FROM item")
    assert str(DEFAULT_LIMIT) in sql


def test_schema_lists_core_tables():
    schema = build_schema()
    for t in ["item", "stock", "partner", "orderline", "voucher"]:
        assert t in schema
    # 예약어 테이블은 큰따옴표 표기
    assert '"order"' in schema
