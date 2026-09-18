"""실행 에이전트: 자연어 → 구조화 제안(plan) → 실제 실행(apply).

plan은 LLM(로컬 Ollama)이 JSON만 생성하게 해서 DB를 건드리지 않고 '제안'만 만든다.
apply는 사용자가 확인한 제안을 받아 기존 모델·검증 규칙으로 실제 쓰기를 수행한다.
"""
import json
import os
from datetime import date
from typing import Any

import httpx
from sqlmodel import Session, select

from ..database import engine
from ..models import Account, Employee, Expense, Item, Partner, PartnerKind, Role, Stock
from .schema import ENTITY_SPECS, describe_for_prompt

_SYS = (
    "너는 ERP 작업 계획기다. 사용자의 자연어 명령을 아래 엔티티/필드로만 매핑해 "
    "'제안 JSON' 하나로 출력한다. 실제로 실행하지 말고 JSON만 낸다.\n\n"
    "사용 가능한 작업:\n{schema}\n\n"
    "출력 형식(JSON):\n"
    '{{"action":"create|update","entity":"item|partner|expense|account|employee|role",'
    '"target":{{"code":"..."}} 또는 null,"values":{{필드:값}},'
    '"summary":"사람이 읽을 한 줄 요약","warnings":["누락·추정 사항"]}}\n\n'
    "규칙: 스키마에 있는 필드만 사용. 모르는 값은 넣지 말고 warnings에 적는다. "
    "구분·구분값은 코드(supplier/customer 등)로. 금액·수량은 숫자만. "
    "수정(update)은 target에 대상 식별자(code)를 넣는다. 현재 화면: {screen}."
)


def _ollama_json(system: str, user: str) -> dict:
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    r = httpx.post(
        f"{base}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "stream": False,
            "format": "json",          # Ollama가 유효한 JSON만 내도록 강제
            "options": {"temperature": 0},
        },
        timeout=120.0,
    )
    r.raise_for_status()
    content = r.json().get("message", {}).get("content", "{}")
    return json.loads(content)


def _coerce(values: dict, numeric: list[str]) -> dict:
    out = {}
    for k, v in values.items():
        if v is None or v == "":
            continue
        if k in numeric:
            try:
                out[k] = int(float(v))
            except (TypeError, ValueError):
                continue
        else:
            out[k] = v
    return out


# 로컬 모델이 자주 혼동하는 필드명 → 정식 필드명 매핑(엔티티/작업별).
# 예: 품목 수정 시 재고를 등록용 필드 initial_stock로 넣는 실수를 quantity로 교정.
_FIELD_ALIASES: dict[tuple[str, str], dict[str, str]] = {
    ("item", "update"): {
        "initial_stock": "quantity",
        "stock": "quantity",
        "재고": "quantity",
        "수량": "quantity",
    },
}


def _apply_aliases(entity: str, action: str, values: dict) -> dict:
    """별칭 키를 정식 키로 바꾼다. 정식 키가 이미 있으면 그 값을 우선한다."""
    amap = _FIELD_ALIASES.get((entity, action))
    if not amap:
        return values
    out: dict = {}
    for k, v in values.items():
        out.setdefault(amap.get(k, k), v)
    return out


# ---- 품목 대상 해석 -------------------------------------------------------

def _norm(s: str) -> str:
    """비교용 정규화: 공백·언더스코어·하이픈 제거 후 소문자."""
    return "".join(str(s).split()).replace("_", "").replace("-", "").lower()


def _item_catalog(s: Session) -> list[Item]:
    return s.exec(select(Item).order_by(Item.code)).all()


def _items_hint() -> str:
    """update 대상 해석용: 현재 품목 코드-품명 목록을 프롬프트에 주입.

    LLM에 실제 데이터를 주지 않으면 품명에서 code를 지어내(환각) 대상 조회가
    실패한다. 등록된 품목을 목록으로 보여주고 그 code만 쓰도록 강제한다.
    """
    with Session(engine) as s:
        items = _item_catalog(s)
    if not items:
        return ""
    listing = "; ".join(f"{it.code}={it.name}" for it in items)
    return (
        "\n\n현재 등록된 품목(수정 시 target.code는 반드시 아래 code 중 하나여야 하며, "
        "품명에서 임의로 코드를 만들지 마라):\n" + listing
    )


def _resolve_item(s: Session, keyval: str) -> Item | None:
    """사용자가 code 또는 품명 어느 쪽으로 지칭해도 실제 품목 행을 찾는다."""
    kv = str(keyval).strip()
    row = s.exec(select(Item).where(Item.code == kv)).first()
    if row:
        return row
    row = s.exec(select(Item).where(Item.name == kv)).first()
    if row:
        return row
    norm = _norm(kv)
    matches = [
        it for it in _item_catalog(s)
        if norm and (norm in _norm(it.code) or norm in _norm(it.name) or _norm(it.name) in norm)
    ]
    return matches[0] if len(matches) == 1 else None


def plan(screen: str, instruction: str) -> dict:
    """자연어 → 검증된 제안. DB 쓰기 없음."""
    system = _SYS.format(schema=describe_for_prompt(), screen=screen or "(없음)") + _items_hint()
    try:
        raw = _ollama_json(system, instruction)
    except httpx.ConnectError:
        return {"ok": False, "error": "로컬 LLM(Ollama)에 연결할 수 없습니다."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"계획 생성 오류: {e}"}

    action = raw.get("action")
    entity = raw.get("entity")
    if entity not in ENTITY_SPECS:
        return {"ok": False, "error": f"지원하지 않는 대상입니다: {entity}"}
    if action not in ("create", "update"):
        return {"ok": False, "error": f"지원하지 않는 작업입니다: {action}"}
    spec = ENTITY_SPECS[entity]
    if action == "update" and "update" not in spec:
        return {"ok": False, "error": f"{spec['label']}은(는) 아직 수정 자동화를 지원하지 않습니다(등록만 가능)."}

    sub = spec[action]
    allowed = set(sub["fields"].keys())
    raw_values = _apply_aliases(entity, action, dict(raw.get("values") or {}))
    values = {k: v for k, v in raw_values.items() if k in allowed}
    values = _coerce(values, sub.get("numeric", []))
    warnings = list(raw.get("warnings") or [])

    target = None
    if action == "create":
        for k, dv in sub.get("defaults", {}).items():
            values.setdefault(k, dv)
        missing = [f for f in sub["required"] if not values.get(f)]
        if missing:
            warnings.append(f"필수 항목 누락: {', '.join(missing)} — 값을 채워 다시 시도하세요.")
    else:  # update: 대상 해석
        key = sub["key"]
        keyval = (raw.get("target") or {}).get(key) or values.pop(key, None)
        if not keyval:
            return {"ok": False, "error": f"수정 대상을 못 찾았습니다({key} 필요)."}
        with Session(engine) as s:
            row = _resolve_item(s, keyval) if entity == "item" else None
            if not row:
                avail = ", ".join(f"{it.code}({it.name})" for it in _item_catalog(s))
                hint = f" 등록된 품목: {avail}" if avail else ""
                return {"ok": False, "error": f"대상을 찾을 수 없습니다: {key}={keyval}.{hint}"}
            # 실제 행의 code로 대상을 고정(모델이 품명으로 지칭했어도 정규화).
            target = {key: row.code, "id": row.id}
        if not values:
            return {"ok": False, "error": "변경할 내용이 없습니다."}

    return {
        "ok": True,
        "action": action,
        "entity": entity,
        "entity_label": spec["label"],
        "values": values,
        "target": target,
        "summary": raw.get("summary") or f"{spec['label']} {action}",
        "warnings": warnings,
    }


# ---- 실행 ----------------------------------------------------------------

def apply_proposal(p: dict) -> dict:
    """확인된 제안을 실제로 실행한다(기존 모델·검증 규칙)."""
    entity, action, values = p.get("entity"), p.get("action"), dict(p.get("values") or {})
    if entity not in ENTITY_SPECS:
        return {"ok": False, "error": "지원하지 않는 대상"}
    with Session(engine) as s:
        try:
            if entity == "item" and action == "create":
                if s.exec(select(Item).where(Item.code == values.get("code"))).first():
                    return {"ok": False, "error": "이미 존재하는 품목 코드입니다."}
                qty = values.pop("initial_stock", 0)
                item = Item(**{k: values[k] for k in values if k != "initial_stock"})
                s.add(item); s.flush()
                s.add(Stock(item_id=item.id, quantity=qty))
                s.commit()
                return {"ok": True, "message": f"품목 '{item.name}' 등록 완료", "id": item.id}

            if entity == "item" and action == "update":
                item = s.get(Item, p["target"]["id"])
                if not item:
                    return {"ok": False, "error": "대상 품목이 없습니다."}
                for k in ("name", "unit", "purchase_price", "sale_price", "safety_stock"):
                    if k in values:
                        setattr(item, k, values[k])
                if "quantity" in values:
                    stock = s.exec(select(Stock).where(Stock.item_id == item.id)).first() or Stock(item_id=item.id)
                    stock.quantity = values["quantity"]
                    s.add(stock)
                s.add(item); s.commit()
                return {"ok": True, "message": f"품목 '{item.name}' 수정 완료", "id": item.id}

            if entity == "partner":
                p_ = Partner(name=values["name"], kind=PartnerKind(values.get("kind", "supplier")),
                             phone=values.get("phone"), biz_no=values.get("biz_no"))
                s.add(p_); s.commit()
                return {"ok": True, "message": f"거래처 '{p_.name}' 등록 완료", "id": p_.id}

            if entity == "account":
                if s.exec(select(Account).where(Account.code == values.get("code"))).first():
                    return {"ok": False, "error": "이미 존재하는 계정 코드입니다."}
                a = Account(code=values["code"], name=values["name"],
                            category=values.get("category", "비용"),
                            entry_side=values.get("entry_side", "차변"), memo=values.get("memo"))
                s.add(a); s.commit()
                return {"ok": True, "message": f"계정과목 '{a.name}' 등록 완료", "id": a.id}

            if entity == "expense":
                x = Expense(expense_date=date.fromisoformat(values["expense_date"]),
                            account=values["account"], memo=values.get("memo"),
                            dept=values.get("dept"), method=values.get("method", "법인카드"),
                            amount=int(values.get("amount", 0)))
                s.add(x); s.commit()
                return {"ok": True, "message": f"비용 '{x.account}' 등록 완료", "id": x.id}

            if entity == "employee":
                hd = values.get("hire_date")
                e = Employee(name=values["name"], department=values.get("department"),
                             position=values.get("position"),
                             hire_date=date.fromisoformat(hd) if hd else None)
                s.add(e); s.commit()
                return {"ok": True, "message": f"직원 '{e.name}' 등록 완료", "id": e.id}

            if entity == "role":
                if s.exec(select(Role).where(Role.name == values.get("name"))).first():
                    return {"ok": False, "error": "이미 존재하는 역할명입니다."}
                r_ = Role(name=values["name"], description=values.get("description"),
                          permissions=values.get("permissions") or [])
                s.add(r_); s.commit()
                return {"ok": True, "message": f"역할 '{r_.name}' 등록 완료", "id": r_.id}

            return {"ok": False, "error": "지원하지 않는 작업 조합"}
        except KeyError as e:
            return {"ok": False, "error": f"필수 값 누락: {e}"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"실행 오류: {e}"}
