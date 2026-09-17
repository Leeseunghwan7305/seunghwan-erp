from datetime import date

from sqlmodel import Session, select

from .database import engine
from .models import Account, Employee, Expense, Item, Partner, PartnerKind, Role, Stock


def seed() -> None:
    """샘플(시드) 데이터 삽입 — 테이블별로 비어있을 때만 채운다(기존 데이터 보존)."""
    with Session(engine) as session:
        _seed_core(session)
        _seed_accounting(session)
        _seed_roles(session)


def _seed_roles(session: Session) -> None:
    if session.exec(select(Role)).first():
        return
    session.add_all([
        Role(name="관리자", description="전체 모듈 접근", permissions=["dashboard", "ai", "sales", "accounting", "hr", "admin"]),
        Role(name="매니저", description="영업·회계·인사 접근", permissions=["dashboard", "sales", "accounting", "hr"]),
        Role(name="일반사원", description="영업·AI 열람", permissions=["dashboard", "sales", "ai"]),
    ])
    session.commit()


def _seed_core(session: Session) -> None:
    if session.exec(select(Item)).first():
        return  # 품목/거래처/직원 이미 시드됨

    items = [
        Item(code="A-001", name="생수 500ml", unit="BOX", purchase_price=4000, sale_price=6000, safety_stock=20),
        Item(code="A-002", name="탄산수 350ml", unit="BOX", purchase_price=6000, sale_price=9000, safety_stock=15),
        Item(code="B-001", name="종이컵 1000입", unit="EA", purchase_price=8000, sale_price=12000, safety_stock=10),
        Item(code="B-002", name="위생장갑 100매", unit="EA", purchase_price=2000, sale_price=3500, safety_stock=30),
        Item(code="C-001", name="주방세제 1L", unit="EA", purchase_price=3000, sale_price=5000, safety_stock=25),
    ]
    session.add_all(items)
    session.flush()

    initial = {"A-001": 50, "A-002": 8, "B-001": 40, "B-002": 12, "C-001": 60}
    for it in items:
        session.add(Stock(item_id=it.id, quantity=initial.get(it.code, 0)))

    session.add_all([
        Partner(name="대성물류", kind=PartnerKind.supplier, phone="02-111-2222", biz_no="111-11-11111"),
        Partner(name="한빛유통", kind=PartnerKind.supplier, phone="02-333-4444", biz_no="222-22-22222"),
        Partner(name="행복마트 강남점", kind=PartnerKind.customer, phone="02-555-6666", biz_no="333-33-33333"),
        Partner(name="싱싱편의점", kind=PartnerKind.customer, phone="02-777-8888", biz_no="444-44-44444"),
    ])

    session.add_all([
        Employee(name="김영업", department="영업부", position="대리", hire_date=date(2023, 3, 2)),
        Employee(name="이재고", department="물류부", position="사원", hire_date=date(2024, 1, 15)),
        Employee(name="박회계", department="관리부", position="과장", hire_date=date(2021, 7, 1)),
    ])

    session.commit()


def _seed_accounting(session: Session) -> None:
    if not session.exec(select(Account)).first():
        session.add_all([
            Account(code="101", name="현금", category="자산", entry_side="차변", memo="보유 현금"),
            Account(code="108", name="외상매출금", category="자산", entry_side="차변", memo="미수금"),
            Account(code="251", name="외상매입금", category="부채", entry_side="대변", memo="미지급금"),
            Account(code="401", name="상품매출", category="수익", entry_side="대변", memo="판매 수익"),
            Account(code="451", name="상품매입", category="비용", entry_side="차변", memo="매입 원가"),
            Account(code="811", name="복리후생비", category="비용", entry_side="차변", memo="직원 복리"),
            Account(code="819", name="임차료", category="비용", entry_side="차변", memo="사무실 월세"),
        ])
        session.commit()

    if not session.exec(select(Expense)).first():
        session.add_all([
            Expense(expense_date=date(2026, 9, 2), account="임차료", memo="9월 사무실 월세", dept="총무", method="계좌이체", amount=1500000),
            Expense(expense_date=date(2026, 9, 5), account="복리후생비", memo="직원 중식대", dept="전사", method="법인카드", amount=320000),
            Expense(expense_date=date(2026, 9, 10), account="소모품비", memo="포장 자재", dept="물류", method="현금", amount=96000),
            Expense(expense_date=date(2026, 9, 12), account="광고선전비", memo="온라인 광고", dept="마케팅", method="법인카드", amount=450000),
        ])
        session.commit()
