"""seunghwan-erp MCP 서버 — ERP 조회 도구를 Model Context Protocol로 노출.

Claude Desktop 등 외부 MCP 클라이언트가 이 서버에 연결하면, 챗봇이 쓰는 것과
동일한 ERP 도구(현황·재고·주문·거래처·문서검색)를 그대로 호출할 수 있다.
내부적으로 `app.chat.tools.execute_tool`을 재사용하므로 로직 중복이 없고,
모든 호출은 기존 감사 로그(AuditLog)에 `actor="mcp"`로 남는다. (읽기 전용)

실행(stdio):
    .venv/bin/python backend/mcp_server.py

Claude Desktop 등록 예시(claude_desktop_config.json):
    {
      "mcpServers": {
        "seunghwan-erp": {
          "command": "/절대경로/seunghwan-erp/.venv/bin/python",
          "args": ["/절대경로/seunghwan-erp/backend/mcp_server.py"]
        }
      }
    }
"""
import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))  # `app` 패키지 임포트 경로

# .env(루트)를 명시적으로 로드해 DATABASE_URL 등을 어느 cwd에서 실행해도 보장한다.
try:
    from dotenv import load_dotenv

    load_dotenv(_BACKEND.parent / ".env")
except Exception:  # noqa: BLE001
    pass

from mcp.server.mcpserver import MCPServer  # noqa: E402

from app.chat.tools import execute_tool  # noqa: E402

server = MCPServer(
    name="seunghwan-erp",
    instructions=(
        "제조·유통 ERP의 실시간 데이터(현황·재고·주문·거래처)와 사내 지식 문서를 "
        "조회하는 읽기 전용 도구 모음. 재고·주문 같은 실시간 수치는 해당 도구로, "
        "규정·매뉴얼 같은 문서 내용은 search_documents로 조회하라."
    ),
)


def _json(result: object) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)


@server.tool(description="매출·매입·미수금·미지급금·재고 요약 등 전체 현황 지표를 조회한다.")
def get_dashboard() -> str:
    return _json(execute_tool("get_dashboard", {}, actor="mcp"))


@server.tool(
    description="품목과 현재 재고를 조회한다. query에 품명/코드 일부를 주면 필터링, "
    "below_safety=true면 안전재고 미달 품목만 반환한다."
)
def get_inventory(query: str = "", below_safety: bool = False) -> str:
    return _json(
        execute_tool("get_inventory", {"query": query, "below_safety": below_safety}, actor="mcp")
    )


@server.tool(
    description="주문(발주/수주) 목록을 조회한다. order_type(purchase/sale), "
    "status(draft/confirmed/done)로 필터할 수 있다."
)
def list_orders(order_type: str = "", status: str = "") -> str:
    args: dict = {}
    if order_type:
        args["order_type"] = order_type
    if status:
        args["status"] = status
    return _json(execute_tool("list_orders", args, actor="mcp"))


@server.tool(description="거래처 목록을 조회한다. kind(supplier=공급처, customer=고객)로 필터할 수 있다.")
def list_partners(kind: str = "") -> str:
    args = {"kind": kind} if kind else {}
    return _json(execute_tool("list_partners", args, actor="mcp"))


@server.tool(
    description="업로드된 사내 지식 문서(매뉴얼·규정·계약서 등)에서 query와 관련된 내용을 검색한다."
)
def search_documents(query: str) -> str:
    return _json(execute_tool("search_documents", {"query": query}, actor="mcp"))


if __name__ == "__main__":
    server.run(transport="stdio")
