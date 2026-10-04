"""백엔드 핵심 로직 유닛테스트 (DB·Ollama 불필요 — 순수 로직만)."""
from app.chat.tools import TOOL_DEFS
from app.chat import providers as p


def test_tool_defs_wellformed():
    names = set()
    for t in TOOL_DEFS:
        assert isinstance(t["name"], str) and t["name"]
        assert t["description"]
        assert t["parameters"]["type"] == "object"
        names.add(t["name"])
    assert {"get_inventory", "get_dashboard", "search_documents", "web_search", "get_chart"} <= names


def test_get_chart_kinds():
    chart = next(t for t in TOOL_DEFS if t["name"] == "get_chart")
    kinds = chart["parameters"]["properties"]["kind"]["enum"]
    assert set(kinds) == {"stock", "receivable", "orders_by_month", "sales_purchase"}


def test_agent_prompt_shares_identity():
    # 3개 provider가 공유하는 에이전트 정체성/리즈닝이 시스템 프롬프트에 포함
    assert "원장" in p.SYSTEM_PROMPT
    assert "사고 절차" in p.SYSTEM_PROMPT


def test_guard_blocks_ungrounded(monkeypatch):
    monkeypatch.setattr(p, "STRICT_GROUNDING", True)
    # 근거(문서/도구) 없으면 차단
    assert p._guard_answer("지어낸 답", has_doc=False, used_tool=False) == p.NO_GROUND_MSG
    # 근거 있으면 원문 유지
    assert p._guard_answer("문서 근거 답", has_doc=True, used_tool=False) == "문서 근거 답"
    assert p._guard_answer("도구 근거 답", has_doc=False, used_tool=True) == "도구 근거 답"


def test_guard_off_passes_through(monkeypatch):
    monkeypatch.setattr(p, "STRICT_GROUNDING", False)
    assert p._guard_answer("자유 답변", has_doc=False, used_tool=False) == "자유 답변"
