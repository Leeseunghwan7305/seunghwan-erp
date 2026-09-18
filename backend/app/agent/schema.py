"""실행(쓰기) 에이전트가 다룰 수 있는 엔티티·필드 스펙.

이 스펙 하나로 (1) LLM 프롬프트 설명 (2) 제안 검증·기본값·숫자 변환을 모두 처리한다.
1차 범위: create 6종(item·partner·expense·account·employee·role) + item update(코드로 대상 지정).
"""
from typing import Any

# entity -> {label, create:{...}, update?:{...}}
ENTITY_SPECS: dict[str, dict[str, Any]] = {
    "item": {
        "label": "품목",
        "create": {
            "required": ["code", "name"],
            "fields": {
                "code": "코드(문자열, 중복 불가)",
                "name": "품명(문자열)",
                "unit": "단위(문자열, 기본 EA)",
                "purchase_price": "매입가(정수)",
                "sale_price": "판매가(정수)",
                "safety_stock": "안전재고(정수)",
                "initial_stock": "초기 재고 수량(정수)",
            },
            "defaults": {"unit": "EA", "purchase_price": 0, "sale_price": 0,
                         "safety_stock": 0, "initial_stock": 0},
            "numeric": ["purchase_price", "sale_price", "safety_stock", "initial_stock"],
        },
        "update": {
            "key": "code",  # 대상 지정 필드
            "fields": {
                "name": "품명", "unit": "단위",
                "purchase_price": "매입가(정수)", "sale_price": "판매가(정수)",
                "safety_stock": "안전재고(정수)", "quantity": "현재 재고를 이 수량으로 변경(정수, 재고 수정 시 이 필드 사용)",
            },
            "numeric": ["purchase_price", "sale_price", "safety_stock", "quantity"],
        },
    },
    "partner": {
        "label": "거래처",
        "create": {
            "required": ["name", "kind"],
            "fields": {
                "name": "거래처명", "kind": "구분(supplier=공급처 / customer=고객)",
                "phone": "연락처", "biz_no": "사업자번호",
            },
            "defaults": {"kind": "supplier"},
            "numeric": [],
        },
    },
    "expense": {
        "label": "비용",
        "create": {
            "required": ["expense_date", "account", "amount"],
            "fields": {
                "expense_date": "일자(YYYY-MM-DD)", "account": "계정과목명",
                "memo": "적요", "dept": "부서",
                "method": "결제수단(법인카드/현금/계좌이체)", "amount": "금액(정수)",
            },
            "defaults": {"method": "법인카드"},
            "numeric": ["amount"],
        },
    },
    "account": {
        "label": "계정과목",
        "create": {
            "required": ["code", "name"],
            "fields": {
                "code": "코드(중복 불가)", "name": "계정과목명",
                "category": "구분(자산/부채/자본/수익/비용)",
                "entry_side": "차대(차변/대변)", "memo": "비고",
            },
            "defaults": {"category": "비용", "entry_side": "차변"},
            "numeric": [],
        },
    },
    "employee": {
        "label": "직원",
        "create": {
            "required": ["name"],
            "fields": {
                "name": "이름", "department": "부서", "position": "직급",
                "hire_date": "입사일(YYYY-MM-DD)",
            },
            "defaults": {},
            "numeric": [],
        },
    },
    "role": {
        "label": "역할(권한)",
        "create": {
            "required": ["name"],
            "fields": {
                "name": "역할명", "description": "설명",
                "permissions": "접근 모듈 목록(dashboard/ai/sales/accounting/hr/admin 중 배열)",
            },
            "defaults": {"permissions": []},
            "numeric": [],
        },
    },
}


def describe_for_prompt() -> str:
    """LLM에게 줄 엔티티/필드 설명 텍스트."""
    lines = []
    for ent, spec in ENTITY_SPECS.items():
        c = spec["create"]
        req = ", ".join(c["required"])
        fields = "; ".join(f"{k}={v}" for k, v in c["fields"].items())
        lines.append(f"- {ent} ({spec['label']}) 등록: 필수[{req}] / 필드: {fields}")
        if "update" in spec:
            u = spec["update"]
            uf = "; ".join(f"{k}={v}" for k, v in u["fields"].items())
            lines.append(f"  · {ent} 수정: {u['key']}로 대상 지정 / 변경 가능: {uf}")
    return "\n".join(lines)
