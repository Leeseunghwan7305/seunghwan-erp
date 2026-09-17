"""사내 ERP 운영 지식 문서(RAG용)를 PDF로 생성한다.

한글은 reportlab 내장 CID 폰트(HYSMyeongJo/HYGothic)로 렌더하므로 별도 폰트 파일이
필요 없다. 내용의 정본은 docs/erp-internal-knowledge.md 이며, 이 스크립트는 동일 내용을
매뉴얼체 PDF로 조판한다. "물류 원장" 팔레트를 사용.

사용법: .venv/bin/python docs/build_knowledge_pdf.py
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---- 폰트 (내장 한글 CID) -------------------------------------------------
pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))  # 본문(명조)
pdfmetrics.registerFont(UnicodeCIDFont("HYGothic-Medium"))     # 제목/라벨(고딕)
BODY = "HYSMyeongJo-Medium"
HEAD = "HYGothic-Medium"

# ---- 물류 원장 팔레트 -----------------------------------------------------
INK = colors.HexColor("#17242a")
BRAND = colors.HexColor("#0f6e5a")
ORANGE = colors.HexColor("#c2622c")
PAPER = colors.HexColor("#eceee8")
SURFACE = colors.HexColor("#f6f7f2")
LINE = colors.HexColor("#d3d7cd")
MUTED = colors.HexColor("#5d6a68")
DANGER_BG = colors.HexColor("#f7e6da")

# ---- 스타일 ---------------------------------------------------------------
styles = getSampleStyleSheet()


def _st(name, **kw):
    return ParagraphStyle(name, parent=styles["Normal"], **kw)


S = {
    "title": _st("t", fontName=HEAD, fontSize=22, leading=27, textColor=INK, spaceAfter=2),
    "subtitle": _st("st", fontName=BODY, fontSize=10, leading=15, textColor=MUTED),
    "callout": _st("co", fontName=BODY, fontSize=8.5, leading=13, textColor=MUTED),
    "h2": _st("h2", fontName=HEAD, fontSize=14.5, leading=19, textColor=BRAND, spaceBefore=16, spaceAfter=6),
    "h3": _st("h3", fontName=HEAD, fontSize=11, leading=15, textColor=INK, spaceBefore=10, spaceAfter=4),
    "body": _st("b", fontName=BODY, fontSize=9.5, leading=15, textColor=INK, alignment=TA_LEFT),
    "li": _st("li", fontName=BODY, fontSize=9.5, leading=14.5, textColor=INK),
    "cell": _st("c", fontName=BODY, fontSize=8.5, leading=12, textColor=INK),
    "cellb": _st("cb", fontName=HEAD, fontSize=8.5, leading=12, textColor=INK),
    "th": _st("th", fontName=HEAD, fontSize=8.5, leading=12, textColor=colors.white),
    "foot": _st("f", fontName=BODY, fontSize=7.5, leading=11, textColor=MUTED),
}


def P(text, style="body"):
    return Paragraph(text, S[style])


def bullets(items):
    return ListFlowable(
        [ListItem(P(t, "li"), leftIndent=6, value="•") for t in items],
        bulletType="bullet", bulletColor=BRAND, bulletFontSize=8,
        leftIndent=10, spaceBefore=2, spaceAfter=6,
    )


def numbers(items):
    return ListFlowable(
        [ListItem(P(t, "li"), leftIndent=6) for t in items],
        bulletType="1", bulletColor=BRAND, bulletFontName=HEAD, bulletFontSize=9,
        leftIndent=14, spaceBefore=2, spaceAfter=6,
    )


def _cells(row, header=False, danger_col=None, danger_val=None):
    style = "th" if header else "cell"
    out = []
    for i, v in enumerate(row):
        s = style
        if not header and i == 0:
            s = "cellb"
        out.append(P(str(v), s))
    return out


def table(header, rows, widths, aligns=None, danger_rows=None):
    """danger_rows: 강조(경고)할 데이터 행 인덱스 집합(0-base, 데이터 기준)."""
    danger_rows = danger_rows or set()
    data = [_cells(header, header=True)]
    for r in rows:
        data.append(_cells(r))
    t = Table(data, colWidths=widths, repeatRows=1)
    ts = [
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SURFACE]),
    ]
    for dr in danger_rows:
        ts.append(("BACKGROUND", (0, dr + 1), (-1, dr + 1), DANGER_BG))
        ts.append(("TEXTCOLOR", (0, dr + 1), (-1, dr + 1), ORANGE))
    if aligns:
        for col, al in aligns.items():
            ts.append(("ALIGN", (col, 1), (col, -1), al))
    t.setStyle(TableStyle(ts))
    return t


# ---- 헤더/푸터 ------------------------------------------------------------
def _decor(canvas, doc):
    canvas.saveState()
    # 상단 브랜드 바
    canvas.setFillColor(BRAND)
    canvas.rect(0, A4[1] - 6, A4[0], 6, fill=1, stroke=0)
    # 러닝 헤더
    canvas.setFont(HEAD, 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, A4[1] - 12 * mm, "seunghwan-erp · 사내 운영 지식 문서")
    canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 12 * mm, "RAG 내부 문서 · 기준일 2026-09-16")
    # 푸터 페이지 번호
    canvas.setFont(BODY, 7.5)
    canvas.drawCentredString(A4[0] / 2, 12 * mm, f"- {doc.page} -")
    canvas.restoreState()


# ---- 문서 조립 ------------------------------------------------------------
def build(out_path: Path):
    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=18 * mm,
        title="사내 ERP 운영 지식 문서", author="seunghwan-erp",
    )
    W = doc.width
    e = []  # elements

    # --- 표지 헤더 ---
    e.append(P("사내 ERP 운영 지식 문서", "title"))
    e.append(P("AI 업무 보조 챗봇(RAG) 인덱싱용 내부 문서", "subtitle"))
    e.append(Spacer(1, 6))
    e.append(HRFlowable(width="100%", thickness=1.2, color=INK, spaceAfter=8))
    e.append(P(
        "<b>기준일</b> 2026-09-16 &nbsp;·&nbsp; <b>범위</b> 회사·조직 / 업무 규정(SOP) / "
        "용어집·데이터 사전 / 현재 데이터 스냅샷", "callout"))
    e.append(P(
        "재고·주문·정산의 실시간 수치는 ERP 조회 도구(get_inventory, list_orders 등)를 우선 사용한다. "
        "본 문서는 도구로 답할 수 없는 규정·용어·맥락과 기준일 스냅샷을 제공한다.", "callout"))

    # --- 1. 회사·조직 ---
    e.append(P("1. 회사·조직 정보", "h2"))
    e.append(P("1.1 회사 개요", "h3"))
    e.append(bullets([
        "<b>업종</b> — 생활용품·음료 유통(도소매)",
        "<b>핵심 업무 흐름</b> — 구매(발주) → 입고·재고 → 판매(수주) → 출고 → 정산(전표)",
        "<b>창고</b> — 단일 물류창고 MAIN (품목별 재고는 MAIN 기준 단일 레코드)",
        "<b>통화 단위</b> — 원(KRW), 모든 금액·단가는 정수로 관리",
    ]))
    e.append(P("1.2 부서 구성", "h3"))
    e.append(table(
        ["부서", "담당 업무"],
        [["영업부", "고객 관리, 수주(판매) 접수, 매출 관리"],
         ["물류부", "재고 관리, 발주·입고, 안전재고 모니터링"],
         ["관리부", "회계·정산, 전표 관리, 경비 처리"]],
        [W * 0.22, W * 0.78],
    ))
    e.append(Spacer(1, 6))
    e.append(P("1.3 직원 명단 (기준일 현재)", "h3"))
    e.append(table(
        ["성명", "부서", "직급", "입사일"],
        [["김영업", "영업부", "대리", "2023-03-02"],
         ["이재고", "물류부", "사원", "2024-01-15"],
         ["박회계", "관리부", "과장", "2021-07-01"]],
        [W * 0.25, W * 0.25, W * 0.2, W * 0.3],
    ))

    # --- 2. SOP ---
    e.append(P("2. 업무 규정·프로세스 (SOP)", "h2"))
    e.append(P("2.1 발주(구매) 프로세스", "h3"))
    e.append(numbers([
        "<b>발주 판단</b> — 현재고가 안전재고 미만이거나 수요 예측상 부족이 예상되면 발주 대상으로 선정한다.",
        "<b>발주서 작성</b> — 공급처(supplier)를 지정해 발주서를 draft(작성) 상태로 생성한다. 품목·수량·매입단가를 입력하면 라인 금액과 합계가 계산된다.",
        "<b>발주 확정</b> — confirmed(확정)로 전환하면 입고 수량이 재고에 자동 가산되고, 매입 전표(미지급)가 자동 생성된다.",
        "<b>입고 완료</b> — 물리적 입고가 끝나면 done 상태로 마감한다.",
        "<b>대금 지급</b> — 매입 전표 대금을 지급하면 결제상태를 paid로 갱신한다. 미지급 전표 합계가 미지급금이다.",
    ]))
    e.append(P("2.2 수주(판매) 프로세스", "h3"))
    e.append(numbers([
        "<b>수주 접수</b> — 고객(customer)의 주문을 접수하고 수주서를 draft로 생성한다. 품목·수량·판매단가를 입력한다.",
        "<b>수주 확정</b> — confirmed로 전환하면 출고 수량만큼 재고가 자동 차감되고, 매출 전표(미수)가 자동 생성된다.",
        "<b>출고 완료</b> — 출고가 끝나면 done으로 마감한다.",
        "<b>대금 회수</b> — 매출 대금이 입금되면 전표를 paid로 갱신한다. 미결제 매출 전표 합계가 미수금이다.",
    ]))
    e.append(P("2.3 주문 상태 전이 규칙", "h3"))
    e.append(bullets([
        "상태 흐름: <b>draft(작성) → confirmed(확정) → done(완료)</b>",
        "<b>재고·전표 반영은 오직 confirmed 전환 시점에 1회 발생</b>한다. draft 상태는 재고에 영향을 주지 않는다.",
        "확정 이후 취소·수정은 정합성을 깨뜨리므로 별도 반품/조정 절차로 처리한다(프로토타입 범위 밖).",
    ]))
    e.append(P("2.4 안전재고 관리 규칙", "h3"))
    e.append(bullets([
        "각 품목은 안전재고(safety_stock) 기준을 가진다.",
        "<b>현재고 &lt; 안전재고</b>이면 '안전재고 미달'로 분류하고 발주를 검토한다.",
        "권장 발주량은 최소한 (안전재고 − 현재고) 이상으로 하되, 발주 단위(BOX/EA)와 리드타임을 고려한다.",
    ]))
    e.append(P("2.5 회계·정산 규칙", "h3"))
    e.append(bullets([
        "전표(voucher)는 주문 확정 시 자동 생성되며, 유형은 매입(purchase)·매출(sale)로 나뉜다.",
        "<b>미수금</b> = 결제상태가 미결제(unpaid)인 매출 전표 금액의 합.",
        "<b>미지급금</b> = 결제상태가 미결제(unpaid)인 매입 전표 금액의 합.",
        "경비(expense)는 주문과 무관한 지출(임차료·복리후생비 등)로 별도 관리한다.",
    ]))
    e.append(P("2.6 거래처 운영 규칙", "h3"))
    e.append(bullets([
        "공급처(supplier)에게는 발주(구매)만, 고객(customer)에게는 판매(수주)만 진행한다.",
        "거래처는 사업자번호로 식별하며, 신규 등록 시 상호·구분·연락처·사업자번호를 필수로 입력한다.",
    ]))

    # --- 3. 용어집·데이터 사전 ---
    e.append(P("3. 용어집·데이터 사전", "h2"))
    e.append(P("3.1 핵심 용어", "h3"))
    e.append(table(
        ["용어", "의미"],
        [["발주", "공급처에 물건을 주문하는 구매 행위 (order_type=purchase)"],
         ["수주", "고객으로부터 주문을 받는 판매 행위 (order_type=sale)"],
         ["전표(voucher)", "매입·매출 시 발생하는 회계 증빙. 결제상태를 가진다"],
         ["미수금", "아직 회수하지 못한 매출 대금"],
         ["미지급금", "아직 지급하지 못한 매입 대금"],
         ["안전재고", "품절을 막기 위해 유지해야 하는 최소 재고 수량"]],
        [W * 0.24, W * 0.76],
    ))
    e.append(Spacer(1, 6))
    e.append(P("3.2 테이블 사전", "h3"))
    e.append(table(
        ["테이블", "설명", "주요 필드"],
        [["item", "품목(기준정보)", "code, name, unit, purchase_price, sale_price, safety_stock"],
         ["stock", "품목별 재고(품목당 1행)", "item_id, warehouse, quantity"],
         ["partner", "거래처", "name, kind, phone, biz_no"],
         ["order", "주문(발주/수주) 헤더", "order_type, partner_id, order_date, status, total"],
         ["orderline", "주문 상세 라인", "order_id, item_id, quantity, unit_price, amount"],
         ["voucher", "회계 전표", "voucher_type, order_id, partner_id, amount, payment_status"],
         ["employee", "직원", "name, department, position, hire_date"],
         ["attendance", "근태", "employee_id, work_date, check_in, check_out"],
         ["account", "계정과목", "code, name, category, entry_side"],
         ["expense", "경비 지출", "expense_date, account, dept, method, amount"]],
        [W * 0.16, W * 0.28, W * 0.56],
    ))
    e.append(Spacer(1, 6))
    e.append(P("3.3 코드값 사전 (챗봇 해석용)", "h3"))
    e.append(table(
        ["필드", "코드값", "의미"],
        [["order_type", "purchase", "구매(발주)"],
         ["order_type", "sale", "판매(수주)"],
         ["order.status", "draft", "작성(재고 미반영)"],
         ["order.status", "confirmed", "확정(재고·전표 반영 완료)"],
         ["order.status", "done", "입/출고 완료"],
         ["partner.kind", "supplier", "공급처(구매처)"],
         ["partner.kind", "customer", "고객(판매처)"],
         ["voucher_type", "purchase", "매입"],
         ["voucher_type", "sale", "매출"],
         ["payment_status", "unpaid", "미결제"],
         ["payment_status", "paid", "결제완료"]],
        [W * 0.28, W * 0.24, W * 0.48],
    ))
    e.append(Spacer(1, 6))
    e.append(P("3.4 계정과목표", "h3"))
    e.append(table(
        ["코드", "계정명", "분류", "기입측"],
        [["101", "현금", "자산", "차변"],
         ["108", "외상매출금", "자산", "차변"],
         ["251", "외상매입금", "부채", "대변"],
         ["401", "상품매출", "수익", "대변"],
         ["451", "상품매입", "비용", "차변"],
         ["811", "복리후생비", "비용", "차변"],
         ["819", "임차료", "비용", "차변"]],
        [W * 0.16, W * 0.34, W * 0.25, W * 0.25],
    ))

    # --- 4. 데이터 스냅샷 ---
    e.append(P("4. 현재 데이터 스냅샷 (기준일 2026-09-16)", "h2"))
    e.append(P("아래 수치는 기준일 시점의 값이다. 최신 값은 ERP 조회 도구를 사용할 것.", "callout"))
    e.append(Spacer(1, 4))
    e.append(P("4.1 요약 지표", "h3"))
    e.append(table(
        ["지표", "값"],
        [["품목 수", "5"], ["거래처 수", "4"], ["직원 수", "3"],
         ["총 재고 수량", "190"], ["안전재고 미달 품목 수", "1 (위생장갑 100매)"],
         ["진행 중 주문 수", "1"], ["총매출", "0원"], ["총매입", "120,000원"],
         ["미수금", "0원"], ["미지급금", "120,000원"]],
        [W * 0.45, W * 0.55],
    ))
    e.append(Spacer(1, 6))
    e.append(P("4.2 품목·재고", "h3"))
    e.append(table(
        ["코드", "품명", "단위", "매입가", "판매가", "안전재고", "현재고", "상태"],
        [["A-001", "생수 500ml", "BOX", "4,000", "6,000", "20", "50", "정상"],
         ["A-002", "탄산수 350ml", "BOX", "6,000", "9,000", "15", "28", "정상"],
         ["B-001", "종이컵 1000입", "EA", "8,000", "12,000", "10", "40", "정상"],
         ["B-002", "위생장갑 100매", "EA", "2,000", "3,500", "30", "12", "미달(부족18)"],
         ["C-001", "주방세제 1L", "EA", "3,000", "5,000", "25", "60", "정상"]],
        [W * 0.09, W * 0.21, W * 0.08, W * 0.12, W * 0.12, W * 0.12, W * 0.1, W * 0.16],
        aligns={3: "RIGHT", 4: "RIGHT", 5: "CENTER", 6: "CENTER"},
        danger_rows={3},
    ))
    e.append(Spacer(1, 6))
    e.append(P("4.3 거래처", "h3"))
    e.append(table(
        ["상호", "구분", "연락처", "사업자번호"],
        [["대성물류", "공급처", "02-111-2222", "111-11-11111"],
         ["한빛유통", "공급처", "02-333-4444", "222-22-22222"],
         ["행복마트 강남점", "고객", "02-555-6666", "333-33-33333"],
         ["싱싱편의점", "고객", "02-777-8888", "444-44-44444"]],
        [W * 0.3, W * 0.15, W * 0.28, W * 0.27],
    ))
    e.append(Spacer(1, 6))
    e.append(P("4.4 주문·전표", "h3"))
    e.append(table(
        ["주문", "유형", "거래처", "일자", "상태", "합계", "전표", "결제"],
        [["1", "발주", "대성물류", "2026-09-16", "확정", "120,000", "매입", "미결제"]],
        [W * 0.08, W * 0.1, W * 0.18, W * 0.17, W * 0.11, W * 0.14, W * 0.1, W * 0.12],
        aligns={5: "RIGHT"},
    ))
    e.append(bullets(["주문 #1 상세: 탄산수 350ml × 20 BOX @ 6,000 = 120,000원"]))
    e.append(P("4.5 경비 지출", "h3"))
    e.append(table(
        ["일자", "계정", "부서", "결제수단", "적요", "금액"],
        [["2026-09-02", "임차료", "총무", "계좌이체", "9월 사무실 월세", "1,500,000"],
         ["2026-09-05", "복리후생비", "전사", "법인카드", "직원 중식대", "320,000"],
         ["2026-09-10", "소모품비", "물류", "현금", "포장 자재", "96,000"],
         ["2026-09-12", "광고선전비", "마케팅", "법인카드", "온라인 광고", "450,000"]],
        [W * 0.16, W * 0.16, W * 0.1, W * 0.14, W * 0.26, W * 0.18],
        aligns={5: "RIGHT"},
    ))

    e.append(Spacer(1, 14))
    e.append(HRFlowable(width="100%", thickness=0.6, color=LINE, spaceAfter=6))
    e.append(P(
        "문서 생성 2026-09-16 · 출처 seunghwan-erp 로컬 DB(erp) · "
        "재생성 docs/build_knowledge_pdf.py · 정본 docs/erp-internal-knowledge.md", "foot"))

    doc.build(e, onFirstPage=_decor, onLaterPages=_decor)
    print(f"생성 완료: {out_path}")


if __name__ == "__main__":
    build(Path(__file__).parent / "erp-internal-knowledge.pdf")
