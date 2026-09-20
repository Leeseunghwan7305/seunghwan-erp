"""사내 ERP 운영 지식 문서(RAG용)를 PDF로 생성한다.

한글은 reportlab 내장 CID 폰트(HYSMyeongJo/HYGothic)로 렌더하므로 별도 폰트 파일이
필요 없다. 내용의 정본은 docs/erp-internal-knowledge.md 이며, 이 스크립트는 동일 내용을
매뉴얼체 PDF로 조판한다. "물류 원장" 팔레트를 사용.

조판 구성: 표지 → 목차(페이지번호) → 본문(섹션 번호·헤어라인·콜아웃 박스·정돈된 표).

사용법: .venv/bin/python docs/build_knowledge_pdf.py
"""
import datetime
import json
import os
import urllib.request
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    CondPageBreak,
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

# ---- 폰트 (내장 한글 CID) -------------------------------------------------
pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))  # 본문(명조)
pdfmetrics.registerFont(UnicodeCIDFont("HYGothic-Medium"))     # 제목/라벨(고딕)
BODY = "HYSMyeongJo-Medium"
HEAD = "HYGothic-Medium"

# ---- 물류 원장 팔레트 -----------------------------------------------------
INK = colors.HexColor("#17242a")
INK3 = colors.HexColor("#8b958f")
BRAND = colors.HexColor("#0f6e5a")
BRAND_STRONG = colors.HexColor("#0b5748")
BRAND_TINT = colors.HexColor("#e6efea")
ORANGE = colors.HexColor("#c2622c")
ORANGE_TINT = colors.HexColor("#f6e9dd")
PAPER = colors.HexColor("#eceee8")
SURFACE = colors.HexColor("#f4f6f0")
LINE = colors.HexColor("#d8dcd2")
LINE_STRONG = colors.HexColor("#c3c9bc")
MUTED = colors.HexColor("#5d6a68")
DANGER_BG = ORANGE_TINT

# ---- 스타일 ---------------------------------------------------------------
styles = getSampleStyleSheet()


def _st(name, **kw):
    return ParagraphStyle(name, parent=styles["Normal"], **kw)


S = {
    # 표지
    "cover_eyebrow": _st("ce", fontName=HEAD, fontSize=9, leading=13, textColor=BRAND,
                         tracking=2, spaceAfter=10),
    "cover_title": _st("ct", fontName=HEAD, fontSize=27, leading=34, textColor=INK, spaceAfter=6),
    "cover_sub": _st("cs", fontName=BODY, fontSize=11, leading=17, textColor=MUTED),
    # 목차
    "toc_head": _st("tch", fontName=HEAD, fontSize=15, leading=20, textColor=INK, spaceAfter=10),
    # 섹션/서브
    "sec": _st("SecTitle", fontName=HEAD, fontSize=15, leading=20, textColor=INK,
               spaceBefore=2, spaceAfter=5),
    "sub": _st("SubTitle", fontName=HEAD, fontSize=11.5, leading=16, textColor=BRAND_STRONG,
               spaceBefore=11, spaceAfter=3),
    # 본문
    "body": _st("b", fontName=BODY, fontSize=10, leading=16.5, textColor=INK, alignment=TA_LEFT),
    "li": _st("li", fontName=BODY, fontSize=10, leading=15.5, textColor=INK),
    "callout": _st("co", fontName=BODY, fontSize=9, leading=14.5, textColor=MUTED),
    "note": _st("nt", fontName=BODY, fontSize=9.5, leading=15, textColor=INK),
    "note_lab": _st("ntl", fontName=HEAD, fontSize=8, leading=12, textColor=BRAND, tracking=1),
    "warn_lab": _st("wl", fontName=HEAD, fontSize=8, leading=12, textColor=ORANGE, tracking=1),
    # 표
    "cell": _st("c", fontName=BODY, fontSize=9, leading=13, textColor=INK),
    "cellb": _st("cb", fontName=HEAD, fontSize=9, leading=13, textColor=INK),
    "th": _st("th", fontName=HEAD, fontSize=9, leading=13, textColor=colors.white),
    "mono": _st("mn", fontName=BODY, fontSize=8.5, leading=12.5, textColor=MUTED),
    "foot": _st("f", fontName=BODY, fontSize=7.5, leading=11, textColor=MUTED),
    # 표지 메타 셀
    "meta_k": _st("mk", fontName=HEAD, fontSize=8.5, leading=13, textColor=BRAND),
    "meta_v": _st("mv", fontName=BODY, fontSize=9.5, leading=14, textColor=INK),
}


def _fix(s):
    """가운뎃점 U+00B7(·)은 HY CID 폰트에서 빈칸으로 렌더된다 → U+30FB(・)로 치환."""
    return s.replace("·", "・")


def P(text, style="body"):
    return Paragraph(_fix(text), S[style])


def bullets(items):
    return ListFlowable(
        [ListItem(P(t, "li"), leftIndent=6, value="•") for t in items],
        bulletType="bullet", bulletColor=BRAND, bulletFontSize=9,
        leftIndent=12, spaceBefore=3, spaceAfter=8,
    )


def numbers(items):
    return ListFlowable(
        [ListItem(P(t, "li"), leftIndent=6) for t in items],
        bulletType="1", bulletColor=BRAND, bulletFontName=HEAD, bulletFontSize=9.5,
        leftIndent=16, spaceBefore=3, spaceAfter=8,
    )


# ---- 섹션/서브 헤더 (목차 자동 등록용) ------------------------------------
def sec(num, title):
    """대섹션 헤더 — 번호(브랜드) + 제목 + 헤어라인. TOC level 0."""
    para = Paragraph(
        f'<font name="{HEAD}" color="#0f6e5a">{num:0>2}</font>'
        f'&nbsp;&nbsp;<font name="{HEAD}" color="#17242a">{_fix(title)}</font>',
        S["sec"],
    )
    rule = HRFlowable(width="100%", thickness=1.4, color=BRAND, spaceBefore=3, spaceAfter=9)
    # 제목 Paragraph는 최상위 플로우여야 afterFlowable(TOC 등록)이 잡는다. KeepTogether로 감싸지 않는다.
    return [CondPageBreak(34 * mm), Spacer(1, 6), para, rule]


def sub(title):
    """서브섹션 헤더 — 좌측 브랜드 틱 + 제목. TOC level 1."""
    para = Paragraph(
        f'<font color="#0f6e5a">▍</font>&nbsp;{_fix(title)}', S["sub"]
    )
    return [CondPageBreak(24 * mm), para]


def callout(text, kind="info"):
    """좌측 액센트 바가 있는 라운드 콜아웃 박스."""
    accent = BRAND if kind == "info" else ORANGE
    tint = BRAND_TINT if kind == "info" else ORANGE_TINT
    lab_style = "note_lab" if kind == "info" else "warn_lab"
    label = "참고" if kind == "info" else "중요"
    inner = Table(
        [[P(label, lab_style)], [P(text, "note")]],
        colWidths=["100%"],
    )
    inner.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (0, 0), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 2),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 0),
    ]))
    box = Table([[inner]], colWidths=["100%"])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), tint),
        ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("ROUNDEDCORNERS", [5, 5, 5, 5]),
    ]))
    return [Spacer(1, 3), box, Spacer(1, 8)]


def _cells(row, header=False):
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
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SURFACE]),
        ("LINEBELOW", (0, 1), (-1, -1), 0.35, LINE),
        ("LINEBELOW", (0, 0), (-1, 0), 1.0, BRAND),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE_STRONG),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
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
def _band(canvas):
    canvas.setFillColor(BRAND)
    canvas.rect(0, A4[1] - 6, A4[0], 6, fill=1, stroke=0)


def _footer(canvas, doc):
    canvas.setFont(BODY, 7.5)
    canvas.setFillColor(INK3)
    canvas.drawCentredString(A4[0] / 2, 12 * mm, f"— {doc.page} —")


def _cover_decor(canvas, doc):
    """표지: 상하단 브랜드 바만, 러닝헤더 없음."""
    canvas.saveState()
    _band(canvas)
    canvas.setFillColor(BRAND)
    canvas.rect(0, 0, A4[0], 4, fill=1, stroke=0)
    canvas.restoreState()


def _decor(canvas, doc):
    canvas.saveState()
    _band(canvas)
    canvas.setFont(HEAD, 7.5)
    canvas.setFillColor(INK3)
    canvas.drawString(20 * mm, A4[1] - 12 * mm, "seunghwan-erp ・ 사내 운영 지식 문서")
    canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 12 * mm, "RAG 내부 문서 ・ 기준일 2026-09-16")
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.4)
    canvas.line(20 * mm, A4[1] - 14 * mm, A4[0] - 20 * mm, A4[1] - 14 * mm)
    _footer(canvas, doc)
    canvas.restoreState()


# ---- 데이터 스냅샷 (백엔드 REST API에서 현재 DB 값을 읽어옴) --------------
API = os.getenv("ERP_API", "http://localhost:8000")
_KIND = {"supplier": "공급처", "customer": "고객"}
_OTYPE = {"purchase": "발주", "sale": "수주"}
_OSTAT = {"draft": "작성", "confirmed": "확정", "done": "완료"}
_MOD = {"dashboard": "대시보드", "ai": "AI", "sales": "영업관리",
        "accounting": "회계관리", "hr": "인사관리", "admin": "권한관리"}


def _fetch(ep):
    try:
        with urllib.request.urlopen(f"{API}/{ep}", timeout=10) as r:
            return json.load(r)
    except Exception as ex:  # noqa: BLE001
        print(f"  (경고) {ep} 조회 실패: {ex}")
        return None


def _won(n):
    try:
        return f"₩{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


def snapshot_elements(W):
    """DB의 현재 데이터를 표로 렌더. 백엔드가 꺼져 있으면 빈 리스트."""
    out = []
    today = datetime.date.today().isoformat()
    out += sec("5", f"데이터 스냅샷 (기준일 {today})")
    out += callout(
        "아래는 기준일 시점의 ERP 내부 데이터 스냅샷이다. 품목 마스터·거래처·직원·역할·계정과목·"
        "비용·주문 내역 등 정적 정보를 담는다. <b>재고 수량·주문 합계·매출/미수/미지급 등 실시간으로 "
        "바뀌는 수치는 이 문서에 넣지 않으며</b>, 그 최신 값은 반드시 조회 도구(get_inventory·"
        "get_dashboard·list_orders)로 확인한다.", "warn")

    items = _fetch("items")
    if items:
        # 재고 수량(quantity)은 라이브 수치라 제외 — 도구(get_inventory)로 조회한다.
        out += sub("5.1 품목 마스터 (단가·안전재고)")
        out.append(table(
            ["코드", "품명", "단위", "매입가", "판매가", "안전재고"],
            [[it["code"], it["name"], it["unit"], _won(it["purchase_price"]),
              _won(it["sale_price"]), it["safety_stock"]] for it in items],
            [W * 0.13, W * 0.34, W * 0.11, W * 0.18, W * 0.18, W * 0.10],
            aligns={3: "RIGHT", 4: "RIGHT", 5: "RIGHT"},
        ))
        out.append(Spacer(1, 6))

    partners = _fetch("partners")
    if partners:
        out += sub("5.2 거래처")
        out.append(table(
            ["이름", "구분", "연락처", "사업자번호"],
            [[p["name"], _KIND.get(p["kind"], p["kind"]), p.get("phone") or "-", p.get("biz_no") or "-"]
             for p in partners],
            [W * 0.32, W * 0.14, W * 0.27, W * 0.27],
        ))
        out.append(Spacer(1, 6))

    employees = _fetch("employees")
    if employees:
        out += sub("5.3 직원")
        out.append(table(
            ["이름", "부서", "직급", "입사일", "권한"],
            [[em["name"], em.get("department") or "-", em.get("position") or "-",
              em.get("hire_date") or "-", em.get("role_name") or "미지정"] for em in employees],
            [W * 0.22, W * 0.20, W * 0.16, W * 0.22, W * 0.20],
        ))
        out.append(Spacer(1, 6))

    roles = _fetch("roles")
    if roles:
        out += sub("5.4 역할(권한)")
        out.append(table(
            ["역할명", "설명", "접근 모듈"],
            [[r["name"], r.get("description") or "-",
              ", ".join(_MOD.get(k, k) for k in r.get("permissions", []))] for r in roles],
            [W * 0.18, W * 0.32, W * 0.50],
        ))
        out.append(Spacer(1, 6))

    accounts = _fetch("accounts")
    if accounts:
        out += sub("5.5 계정과목")
        out.append(table(
            ["코드", "계정명", "구분", "차대", "비고"],
            [[a["code"], a["name"], a.get("category") or "-", a.get("entry_side") or "-",
              a.get("memo") or "-"] for a in accounts],
            [W * 0.12, W * 0.28, W * 0.16, W * 0.14, W * 0.30],
        ))
        out.append(Spacer(1, 6))

    expenses = _fetch("expenses")
    if expenses:
        out += sub("5.6 비용 지출 내역")
        out.append(table(
            ["일자", "계정과목", "적요", "부서", "결제", "금액"],
            [[x["expense_date"], x["account"], x.get("memo") or "-", x.get("dept") or "-",
              x.get("method") or "-", _won(x["amount"])] for x in expenses],
            [W * 0.16, W * 0.18, W * 0.24, W * 0.12, W * 0.14, W * 0.16],
            aligns={5: "RIGHT"},
        ))
        out.append(Spacer(1, 6))

    orders = _fetch("orders")
    if orders:
        # 합계(total)는 라이브 수치라 제외 — 매출·주문 금액은 도구(list_orders·get_dashboard)로 조회.
        out += sub("5.7 주문(발주·수주) 내역")
        out.append(table(
            ["번호", "유형", "거래처", "일자", "상태"],
            [[o["id"], _OTYPE.get(o["order_type"], o["order_type"]), o.get("partner_name") or "-",
              o["order_date"], _OSTAT.get(o["status"], o["status"])] for o in orders],
            [W * 0.12, W * 0.14, W * 0.36, W * 0.22, W * 0.16],
        ))
        out.append(Spacer(1, 6))

    return out


# ---- 표지 · 목차 ----------------------------------------------------------
def cover_elements(W):
    e = [Spacer(1, 46 * mm)]
    e.append(P("SEUNGHWAN-ERP · 내부 문서", "cover_eyebrow"))
    e.append(P("사내 ERP 운영 지식 문서", "cover_title"))
    e.append(P("AI 업무 보조 챗봇(RAG) 인덱싱용 내부 문서", "cover_sub"))
    e.append(Spacer(1, 10))
    e.append(HRFlowable(width="38%", thickness=2, color=BRAND, spaceAfter=16, hAlign="LEFT"))

    meta = Table(
        [
            [P("기준일", "meta_k"), P("2026-09-16", "meta_v")],
            [P("범위", "meta_k"), P("회사·조직 / 업무 규정(SOP) / 용어집·데이터 사전 / 기준일 스냅샷", "meta_v")],
            [P("정본", "meta_k"), P("docs/erp-internal-knowledge.md", "meta_v")],
            [P("재생성", "meta_k"), P("docs/build_knowledge_pdf.py", "meta_v")],
        ],
        colWidths=[W * 0.16, W * 0.84],
    )
    meta.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
    ]))
    e.append(meta)
    e.append(Spacer(1, 18))
    e += callout(
        "재고·주문·정산의 실시간 수치는 ERP 조회 도구(get_inventory, list_orders 등)를 우선 사용한다. "
        "본 문서는 도구로 답할 수 없는 규정·용어·맥락과 기준일 스냅샷을 제공한다.", "info")
    e.append(PageBreak())
    return e


def toc_elements():
    toc = TableOfContents()
    toc.dotsMinLevel = 0
    toc.levelStyles = [
        ParagraphStyle("toc0", fontName=HEAD, fontSize=11, leading=20, textColor=INK,
                       spaceBefore=4),
        ParagraphStyle("toc1", fontName=BODY, fontSize=9.5, leading=15, textColor=MUTED,
                       leftIndent=14),
    ]
    return [P("목차", "toc_head"),
            HRFlowable(width="100%", thickness=0.8, color=LINE_STRONG, spaceAfter=8),
            toc, PageBreak()]


# ---- TOC를 위한 DocTemplate ----------------------------------------------
class ManualDoc(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            name = flowable.style.name
            if name == "SecTitle":
                self.notify("TOCEntry", (0, flowable.getPlainText(), self.page))
            elif name == "SubTitle":
                self.notify("TOCEntry", (1, flowable.getPlainText(), self.page))


# ---- 문서 조립 ------------------------------------------------------------
def build(out_path: Path):
    doc = ManualDoc(
        str(out_path), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=18 * mm,
        title="사내 ERP 운영 지식 문서", author="seunghwan-erp",
    )
    W = doc.width
    e = []  # elements

    # --- 표지 + 목차 ---
    e += cover_elements(W)
    e += toc_elements()

    # --- 1. 회사·조직 ---
    e += sec("1", "회사·조직 정보")
    e += sub("1.1 회사 개요")
    e.append(bullets([
        "<b>업종</b> — 생활용품·음료 유통(도소매)",
        "<b>핵심 업무 흐름</b> — 구매(발주) → 입고·재고 → 판매(수주) → 출고 → 정산(전표)",
        "<b>창고</b> — 단일 물류창고 MAIN (품목별 재고는 MAIN 기준 단일 레코드)",
        "<b>통화 단위</b> — 원(KRW), 모든 금액·단가는 정수로 관리",
    ]))
    e += sub("1.2 부서 구성")
    e.append(table(
        ["부서", "담당 업무"],
        [["영업부", "고객 관리, 수주(판매) 접수, 매출 관리"],
         ["물류부", "재고 관리, 발주·입고, 안전재고 모니터링"],
         ["관리부", "회계·정산, 전표 관리, 경비 처리"]],
        [W * 0.22, W * 0.78],
    ))
    e.append(Spacer(1, 6))
    e += sub("1.3 직원 명단")
    e.append(P("전체 직원 명단은 아래 '5.3 직원' 스냅샷을 참고한다. (권한·부서 포함)", "body"))

    # --- 2. SOP ---
    e += sec("2", "업무 규정·프로세스 (SOP)")
    e += sub("2.1 발주(구매) 프로세스")
    e.append(numbers([
        "<b>발주 판단</b> — 현재고가 안전재고 미만이거나 수요 예측상 부족이 예상되면 발주 대상으로 선정한다.",
        "<b>발주서 작성</b> — 공급처(supplier)를 지정해 발주서를 draft(작성) 상태로 생성한다. 품목·수량·매입단가를 입력하면 라인 금액과 합계가 계산된다.",
        "<b>발주 확정</b> — confirmed(확정)로 전환하면 입고 수량이 재고에 자동 가산되고, 매입 전표(미지급)가 자동 생성된다.",
        "<b>입고 완료</b> — 물리적 입고가 끝나면 done 상태로 마감한다.",
        "<b>대금 지급</b> — 매입 전표 대금을 지급하면 결제상태를 paid로 갱신한다. 미지급 전표 합계가 미지급금이다.",
    ]))
    e += sub("2.2 수주(판매) 프로세스")
    e.append(numbers([
        "<b>수주 접수</b> — 고객(customer)의 주문을 접수하고 수주서를 draft로 생성한다. 품목·수량·판매단가를 입력한다.",
        "<b>수주 확정</b> — confirmed로 전환하면 출고 수량만큼 재고가 자동 차감되고, 매출 전표(미수)가 자동 생성된다.",
        "<b>출고 완료</b> — 출고가 끝나면 done으로 마감한다.",
        "<b>대금 회수</b> — 매출 대금이 입금되면 전표를 paid로 갱신한다. 미결제 매출 전표 합계가 미수금이다.",
    ]))
    e += sub("2.3 주문 상태 전이 규칙")
    e += callout(
        "상태 흐름은 <b>draft(작성) → confirmed(확정) → done(완료)</b>이며, "
        "<b>재고·전표 반영은 오직 confirmed 전환 시점에 1회 발생</b>한다. draft 상태는 재고에 영향을 주지 않는다. "
        "확정 이후 취소·수정은 정합성을 깨뜨리므로 별도 반품/조정 절차로 처리한다(프로토타입 범위 밖).", "warn")
    e += sub("2.4 안전재고 관리 규칙")
    e.append(bullets([
        "각 품목은 안전재고(safety_stock) 기준을 가진다.",
        "<b>현재고 &lt; 안전재고</b>이면 '안전재고 미달'로 분류하고 발주를 검토한다.",
        "권장 발주량은 최소한 (안전재고 − 현재고) 이상으로 하되, 발주 단위(BOX/EA)와 리드타임을 고려한다.",
    ]))
    e += sub("2.5 회계·정산 규칙")
    e.append(bullets([
        "전표(voucher)는 주문 확정 시 자동 생성되며, 유형은 매입(purchase)·매출(sale)로 나뉜다.",
        "<b>미수금</b> = 결제상태가 미결제(unpaid)인 매출 전표 금액의 합.",
        "<b>미지급금</b> = 결제상태가 미결제(unpaid)인 매입 전표 금액의 합.",
        "경비(expense)는 주문과 무관한 지출(임차료·복리후생비 등)로 별도 관리한다.",
    ]))
    e += sub("2.6 거래처 운영 규칙")
    e.append(bullets([
        "공급처(supplier)에게는 발주(구매)만, 고객(customer)에게는 판매(수주)만 진행한다.",
        "거래처는 사업자번호로 식별하며, 신규 등록 시 상호·구분·연락처·사업자번호를 필수로 입력한다.",
    ]))

    # --- 3. 용어집·데이터 사전 ---
    e += sec("3", "용어집·데이터 사전")
    e += sub("3.1 핵심 용어")
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
    e += sub("3.2 테이블 사전")
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
    e += sub("3.3 코드값 사전 (챗봇 해석용)")
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
    e += sub("3.4 계정과목표")
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

    # --- 4. 화면별 사용법 (UI 가이드) ---
    e += sec("4", "화면별 사용법 (UI 가이드)")

    e += sub("4.1 로그인·권한·도움말")
    e.append(numbers([
        "로그인 화면(/login)에서 본인 직원을 선택하고 '로그인'을 누른다. (프로토타입은 비밀번호 없이 직원 선택 방식)",
        "좌측 메뉴에는 본인 역할(권한)에 허용된 모듈만 보인다. 권한 없는 화면에 URL로 접근하면 '접근 권한이 없습니다'가 표시된다.",
        "화면 우하단의 '? 도움말' 버튼을 누르면 지금 화면의 사용법을 물어볼 수 있다.",
        "좌측 하단 '로그아웃'으로 로그아웃한다.",
    ]))

    e += sub("4.2 품목 등록·재고 수정 (영업관리 &gt; 품목관리)")
    e.append(numbers([
        "좌측 메뉴에서 영업관리 &gt; 품목관리로 이동한다.",
        "'+ 품목 등록'을 눌러 코드(중복 불가)·품명·단위·매입가·판매가·안전재고·재고 수량을 입력하고 '등록'한다.",
        "단가나 재고 수량을 바꾸려면 해당 행의 '수정'을 누른다(코드는 수정 불가).",
        "현재고가 안전재고보다 적으면 재고가 빨갛게 '미달'로 표시된다.",
    ]))

    e += sub("4.3 거래처 등록 (영업관리 &gt; 거래처관리)")
    e.append(numbers([
        "영업관리 &gt; 거래처관리 &gt; '+ 거래처 등록'.",
        "거래처명·구분(공급처/고객)·연락처·사업자번호를 입력한다. 공급처는 발주, 고객은 수주 대상이다.",
    ]))

    e += sub("4.4 수주 등록·확정 (영업관리 &gt; 수주현황)")
    e.append(numbers([
        "영업관리 &gt; 수주현황 &gt; '+ 수주 등록'.",
        "고객(거래처)을 고르고 '+ 품목 추가'로 품목·수량을 입력한 뒤 '등록'하면 draft(작성) 상태로 생성된다.",
        "'확정'을 누르면 출고 수량만큼 재고가 자동 차감되고 매출 전표(미수)가 생성된다. 재고가 부족하면 확정이 막힌다.",
        "draft 상태만 삭제할 수 있고, 확정된 수주는 삭제할 수 없다.",
    ]))

    e += sub("4.5 직원 등록·권한 지정 (인사관리 &gt; 직원관리)")
    e.append(numbers([
        "인사관리 &gt; 직원관리 &gt; '+ 직원 등록'. 이름·부서·직급·입사일을 입력한다.",
        "직원에게 권한을 주려면 '권한(역할)'에서 역할을 선택한다. 역할은 권한관리에서 미리 만들어 둔다.",
        "이미 등록된 직원의 권한을 바꾸려면 '수정'에서 역할을 다시 고른다.",
    ]))

    e += sub("4.6 역할(권한) 만들기 (인사관리 &gt; 권한관리)")
    e.append(numbers([
        "인사관리 &gt; 권한관리 &gt; '+ 역할 등록'.",
        "역할명·설명을 입력하고, 그 역할이 접근할 모듈(대시보드·AI·영업관리·회계관리·인사관리·권한관리)을 체크한다.",
        "기본 역할은 관리자(전체)·매니저(영업·회계·인사)·일반사원(영업·AI)이며, 직원관리에서 직원에게 지정한다.",
    ]))

    e += sub("4.7 비용 등록 (회계관리 &gt; 비용관리)")
    e.append(numbers([
        "회계관리 &gt; 비용관리 &gt; '+ 비용 등록'.",
        "일자·계정과목·적요·부서·결제수단(법인카드/현금/계좌이체)·금액을 입력한다. 경비는 주문과 무관한 지출이다.",
    ]))

    e += sub("4.8 계정과목 추가 (회계관리 &gt; 계정과목관리)")
    e.append(numbers([
        "회계관리 &gt; 계정과목관리 &gt; '+ 계정과목 등록'.",
        "코드(중복 불가)·계정과목명·구분(자산/부채/자본/수익/비용)·차대(차변/대변)·비고를 입력한다.",
    ]))

    e += sub("4.9 지식 문서 업로드 (AI &gt; 지식 문서)")
    e.append(numbers([
        "AI &gt; 지식 문서에서 파일(txt/md/pdf) 업로드 또는 텍스트 붙여넣기로 문서를 추가한다.",
        "상태가 indexing → ready가 되면 AI 어시스턴트와 도움말이 그 내용을 검색해 답한다.",
    ]))

    # --- 5. 데이터 스냅샷 (DB에서 현재 값을 읽어 렌더) ---
    e.extend(snapshot_elements(W))

    e.append(Spacer(1, 16))
    e.append(HRFlowable(width="100%", thickness=0.6, color=LINE, spaceAfter=6))
    e.append(P(
        "문서 생성 2026-09-16 · 출처 seunghwan-erp 로컬 DB(erp) · "
        "재생성 docs/build_knowledge_pdf.py · 정본 docs/erp-internal-knowledge.md", "foot"))

    doc.multiBuild(e, onFirstPage=_cover_decor, onLaterPages=_decor)
    print(f"생성 완료: {out_path}")


if __name__ == "__main__":
    build(Path(__file__).parent / "erp-internal-knowledge.pdf")
