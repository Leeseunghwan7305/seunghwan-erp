from datetime import date
from typing import Optional

from sqlmodel import SQLModel

from .models import OrderType, PartnerKind


# ---- Item ----------------------------------------------------------------

class ItemCreate(SQLModel):
    code: str
    name: str
    unit: str = "EA"
    purchase_price: int = 0
    sale_price: int = 0
    safety_stock: int = 0
    initial_stock: int = 0   # 등록 시 초기 재고


class ItemRead(SQLModel):
    id: int
    code: str
    name: str
    unit: str
    purchase_price: int
    sale_price: int
    safety_stock: int
    quantity: int = 0        # 현재 재고 (Stock에서 조인)
    below_safety: bool = False


# ---- Partner -------------------------------------------------------------

class PartnerCreate(SQLModel):
    name: str
    kind: PartnerKind
    phone: Optional[str] = None
    biz_no: Optional[str] = None


# ---- Item update ---------------------------------------------------------

class ItemUpdate(SQLModel):
    name: str
    unit: str = "EA"
    purchase_price: int = 0
    sale_price: int = 0
    safety_stock: int = 0
    quantity: int = 0        # 재고 직접 조정


# ---- Employee ------------------------------------------------------------

class EmployeeIn(SQLModel):
    name: str
    department: Optional[str] = None
    position: Optional[str] = None
    hire_date: Optional[date] = None
    role_id: Optional[int] = None


class EmployeeRead(SQLModel):
    id: int
    name: str
    department: Optional[str] = None
    position: Optional[str] = None
    hire_date: Optional[date] = None
    role_id: Optional[int] = None
    role_name: Optional[str] = None


# ---- Role (권한) ----------------------------------------------------------

class RoleIn(SQLModel):
    name: str
    description: Optional[str] = None
    permissions: list[str] = []


# ---- Account (계정과목) ---------------------------------------------------

class AccountIn(SQLModel):
    code: str
    name: str
    category: str = "비용"
    entry_side: str = "차변"
    memo: Optional[str] = None


# ---- Expense (비용) -------------------------------------------------------

class ExpenseIn(SQLModel):
    expense_date: date
    account: str
    memo: Optional[str] = None
    dept: Optional[str] = None
    method: str = "법인카드"
    amount: int = 0


# ---- Order ---------------------------------------------------------------

class OrderLineIn(SQLModel):
    item_id: int
    quantity: int
    unit_price: Optional[int] = None   # 미지정 시 품목 기본가 사용


class OrderCreate(SQLModel):
    order_type: OrderType
    partner_id: int
    lines: list[OrderLineIn]


class OrderLineRead(SQLModel):
    item_id: int
    item_name: str
    quantity: int
    unit_price: int
    amount: int


class OrderRead(SQLModel):
    id: int
    order_type: OrderType
    partner_id: int
    partner_name: str
    order_date: str
    status: str
    total: int
    lines: list[OrderLineRead] = []


# ---- Dashboard -----------------------------------------------------------

class DashboardSummary(SQLModel):
    item_count: int
    partner_count: int
    total_stock_qty: int
    below_safety_count: int
    sales_total: int          # 매출 합계
    purchase_total: int       # 매입 합계
    receivable: int           # 미수금(미결제 매출)
    payable: int              # 미지급금(미결제 매입)
    open_orders: int          # 미완료 주문 수
