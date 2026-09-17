from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


# ---- Enums ---------------------------------------------------------------

class PartnerKind(str, Enum):
    supplier = "supplier"   # 공급처(구매처)
    customer = "customer"   # 고객(판매처)


class OrderType(str, Enum):
    purchase = "purchase"   # 구매(발주)
    sale = "sale"           # 판매(수주)


class OrderStatus(str, Enum):
    draft = "draft"         # 작성
    confirmed = "confirmed" # 확정(재고 반영 완료)
    done = "done"           # 입/출고 완료


class VoucherType(str, Enum):
    purchase = "purchase"   # 매입
    sale = "sale"           # 매출


class PaymentStatus(str, Enum):
    unpaid = "unpaid"       # 미결제
    paid = "paid"           # 결제완료


# ---- 기준정보: 품목 / 재고 ------------------------------------------------

class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    name: str
    unit: str = "EA"
    purchase_price: int = 0        # 매입 단가(원)
    sale_price: int = 0            # 판매 단가(원)
    safety_stock: int = 0          # 안전재고

    stock: Optional["Stock"] = Relationship(back_populates="item")


class Stock(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="item.id", index=True, unique=True)
    warehouse: str = "MAIN"
    quantity: int = 0

    item: Optional[Item] = Relationship(back_populates="stock")


# ---- 거래처 --------------------------------------------------------------

class Partner(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    kind: PartnerKind
    phone: Optional[str] = None
    biz_no: Optional[str] = None   # 사업자번호


# ---- 주문(구매/판매) ------------------------------------------------------

class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_type: OrderType
    partner_id: int = Field(foreign_key="partner.id", index=True)
    order_date: date = Field(default_factory=date.today)
    status: OrderStatus = OrderStatus.draft
    total: int = 0

    lines: list["OrderLine"] = Relationship(
        back_populates="order",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class OrderLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id", index=True)
    item_id: int = Field(foreign_key="item.id", index=True)
    quantity: int
    unit_price: int
    amount: int = 0

    order: Optional[Order] = Relationship(back_populates="lines")


# ---- 회계: 전표 ----------------------------------------------------------

class Voucher(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    voucher_type: VoucherType
    order_id: int = Field(foreign_key="order.id", index=True)
    partner_id: int = Field(foreign_key="partner.id", index=True)
    amount: int = 0
    payment_status: PaymentStatus = PaymentStatus.unpaid
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---- 인사 / 근태 ---------------------------------------------------------

class Employee(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    department: Optional[str] = None
    position: Optional[str] = None
    hire_date: Optional[date] = None
    role_id: Optional[int] = Field(default=None, foreign_key="role.id")


# ---- 권한(역할) ----------------------------------------------------------

class Role(SQLModel, table=True):
    """권한 역할. permissions는 접근 가능한 모듈 키 목록(예: ['sales','hr'])."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: Optional[str] = None
    permissions: list[str] = Field(default_factory=list, sa_column=Column(JSONB))


class Attendance(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    employee_id: int = Field(foreign_key="employee.id", index=True)
    work_date: date = Field(default_factory=date.today)
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    work_hours: float = 0.0


# ---- 회계: 계정과목 / 비용 -----------------------------------------------

class Account(SQLModel, table=True):
    """계정과목(차변/대변 체계). category는 자산/부채/자본/수익/비용."""
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    name: str
    category: str = "비용"          # 자산 / 부채 / 자본 / 수익 / 비용
    entry_side: str = "차변"        # 차변 / 대변
    memo: Optional[str] = None


class Expense(SQLModel, table=True):
    """지출(비용) 내역."""
    id: Optional[int] = Field(default=None, primary_key=True)
    expense_date: date = Field(default_factory=date.today)
    account: str                    # 계정과목명
    memo: Optional[str] = None
    dept: Optional[str] = None
    method: str = "법인카드"         # 결제수단: 법인카드 / 현금 / 계좌이체
    amount: int = 0


# ---- AI: RAG 지식 문서 ----------------------------------------------------

class DocSourceType(str, Enum):
    paste = "paste"   # 텍스트 붙여넣기
    txt = "txt"
    md = "md"
    pdf = "pdf"


class DocStatus(str, Enum):
    indexing = "indexing"   # 추출·청크·임베딩 진행 중
    ready = "ready"         # 검색 가능
    error = "error"         # 인제스트 실패


class Document(SQLModel, table=True):
    """업로드된 지식 문서(원본 메타). 실제 검색 단위는 DocChunk."""
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    source_type: DocSourceType
    filename: Optional[str] = None
    char_count: int = 0
    chunk_count: int = 0
    status: DocStatus = DocStatus.indexing
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    chunks: list["DocChunk"] = Relationship(
        back_populates="document",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class DocChunk(SQLModel, table=True):
    """문서 청크 + bge-m3 임베딩(dim 1024). 임베딩은 JSONB로 저장."""
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    ordinal: int                      # 문서 내 순서(0-base)
    content: str
    embedding: list[float] = Field(default_factory=list, sa_column=Column(JSONB))

    document: Optional[Document] = Relationship(back_populates="chunks")
