"""챗봇 도구 정의(provider 중립) + 실행기.

Phase A: 조회 전용(read-only). 도구는 기존 ERP 데이터를 그대로 조회한다.
"""
from typing import Any

from sqlmodel import Session, select

from ..database import engine
from ..models import (
    Item,
    Order,
    OrderStatus,
    OrderType,
    Partner,
    PartnerKind,
    PaymentStatus,
    Stock,
    Voucher,
    VoucherType,
)

# ---- provider 중립 도구 스키마 -------------------------------------------

TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "get_dashboard",
        "description": "매출·매입·미수금·미지급금·재고 요약 등 전체 현황 지표를 조회한다.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_inventory",
        "description": "품목과 현재 재고를 조회한다. query에 품명/코드 일부를 주면 필터링한다. below_safety=true면 안전재고 미달 품목만 반환.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "품명 또는 코드 검색어(선택)"},
                "below_safety": {"type": "boolean", "description": "안전재고 미달만 볼지 여부(선택)"},
            },
            "required": [],
        },
    },
    {
        "name": "list_orders",
        "description": "주문(발주/수주) 목록을 조회한다. order_type(purchase/sale), status(draft/confirmed/done)로 필터 가능.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_type": {"type": "string", "enum": ["purchase", "sale"]},
                "status": {"type": "string", "enum": ["draft", "confirmed", "done"]},
            },
            "required": [],
        },
    },
    {
        "name": "list_partners",
        "description": "거래처 목록을 조회한다. kind(supplier=공급처, customer=고객)로 필터 가능.",
        "parameters": {
            "type": "object",
            "properties": {"kind": {"type": "string", "enum": ["supplier", "customer"]}},
            "required": [],
        },
    },
    {
        "name": "search_documents",
        "description": "업로드된 사내 지식 문서(매뉴얼·규정·계약서 등)에서 query와 관련된 내용을 검색한다. 재고·주문 같은 구조화 수치가 아닌, 문서에 적힌 내용을 물으면 사용한다.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색할 자연어 질의"},
            },
            "required": ["query"],
        },
    },
]


# ---- 프롬프트용 도구 설명(쿠키 provider용) --------------------------------

def tools_prompt() -> str:
    """웹 세션(claude.ai)엔 tools 파라미터가 없어, 도구 목록과 호출 규약을
    프롬프트 텍스트로 주입한다. 쿠키 provider의 프리앰블에서 사용한다."""
    lines = ["사용 가능한 도구:"]
    for t in TOOL_DEFS:
        props = t["parameters"].get("properties", {})
        if props:
            params = ", ".join(
                f"{k}({v.get('type', 'any')})" for k, v in props.items()
            )
        else:
            params = "(인자 없음)"
        lines.append(f"- {t['name']}: {t['description']} / 인자: {params}")
    lines.append(
        "\n도구가 필요하면 다른 텍스트 없이 아래 JSON 하나만 출력하라:\n"
        '{"tool": "도구이름", "input": {인자들}}\n'
        "도구 결과를 받으면 그 데이터로 사용자에게 한국어로 간결히 최종 답변하라. "
        "도구가 더 필요 없으면 JSON 없이 최종 답변만 출력하라."
    )
    return "\n".join(lines)


# ---- 실행 ----------------------------------------------------------------

def _get_dashboard(session: Session) -> dict:
    items = session.exec(select(Item)).all()
    stocks = {s.item_id: s.quantity for s in session.exec(select(Stock)).all()}
    vouchers = session.exec(select(Voucher)).all()
    orders = session.exec(select(Order)).all()
    partners = session.exec(select(Partner)).all()

    def _sum(vt, unpaid_only=False):
        return sum(
            v.amount
            for v in vouchers
            if v.voucher_type == vt and (not unpaid_only or v.payment_status == PaymentStatus.unpaid)
        )

    return {
        "품목수": len(items),
        "거래처수": len(partners),
        "총재고수량": sum(stocks.values()),
        "안전재고미달품목수": sum(1 for it in items if stocks.get(it.id, 0) < it.safety_stock),
        "총매출": _sum(VoucherType.sale),
        "총매입": _sum(VoucherType.purchase),
        "미수금": _sum(VoucherType.sale, True),
        "미지급금": _sum(VoucherType.purchase, True),
        "진행중주문수": sum(1 for o in orders if o.status != OrderStatus.done),
    }


def _get_inventory(session: Session, query: str | None = None, below_safety: bool = False) -> list[dict]:
    items = session.exec(select(Item)).all()
    stocks = {s.item_id: s.quantity for s in session.exec(select(Stock)).all()}
    out = []
    for it in items:
        qty = stocks.get(it.id, 0)
        if query and query.lower() not in it.name.lower() and query.lower() not in it.code.lower():
            continue
        if below_safety and qty >= it.safety_stock:
            continue
        out.append({
            "코드": it.code,
            "품명": it.name,
            "단위": it.unit,
            "매입가": it.purchase_price,
            "판매가": it.sale_price,
            "현재재고": qty,
            "안전재고": it.safety_stock,
            "안전재고미달": qty < it.safety_stock,
        })
    return out


def _list_orders(session: Session, order_type: str | None = None, status: str | None = None) -> list[dict]:
    orders = session.exec(select(Order).order_by(Order.id.desc())).all()
    out = []
    for o in orders:
        if order_type and o.order_type != OrderType(order_type):
            continue
        if status and o.status != OrderStatus(status):
            continue
        partner = session.get(Partner, o.partner_id)
        out.append({
            "번호": o.id,
            "유형": "발주" if o.order_type == OrderType.purchase else "수주",
            "거래처": partner.name if partner else None,
            "일자": o.order_date.isoformat(),
            "상태": o.status.value,
            "합계": o.total,
            "품목": [{"품명": session.get(Item, l.item_id).name if session.get(Item, l.item_id) else None,
                     "수량": l.quantity} for l in o.lines],
        })
    return out


def _list_partners(session: Session, kind: str | None = None) -> list[dict]:
    partners = session.exec(select(Partner)).all()
    out = []
    for p in partners:
        if kind and p.kind != PartnerKind(kind):
            continue
        out.append({
            "이름": p.name,
            "구분": "공급처" if p.kind == PartnerKind.supplier else "고객",
            "연락처": p.phone,
            "사업자번호": p.biz_no,
        })
    return out


def _search_documents(session: Session, query: str = "") -> Any:
    # 검색은 자체 세션을 여는 retrieval.search를 재사용한다(session 인자 미사용).
    from ..rag.retrieval import search

    results = search(query, top_k=5)
    if not results:
        return {"결과": "관련 문서를 찾지 못했습니다. (업로드된 문서가 없거나 색인 미완일 수 있음)"}
    return [
        {"출처": r["title"], "유사도": r["score"], "내용": r["content"]}
        for r in results
    ]


_HANDLERS = {
    "get_dashboard": _get_dashboard,
    "get_inventory": _get_inventory,
    "list_orders": _list_orders,
    "list_partners": _list_partners,
    "search_documents": _search_documents,
}


def execute_tool(name: str, args: dict[str, Any]) -> Any:
    """도구를 실행하고 JSON 직렬화 가능한 결과를 반환한다."""
    handler = _HANDLERS.get(name)
    if not handler:
        return {"error": f"알 수 없는 도구: {name}"}
    args = args or {}
    with Session(engine) as session:
        try:
            return handler(session, **args)
        except TypeError as e:
            return {"error": f"도구 인자 오류: {e}"}
        except Exception as e:  # noqa: BLE001 - 프로토타입: 오류를 모델에 전달
            return {"error": f"도구 실행 오류: {e}"}
