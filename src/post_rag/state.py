from __future__ import annotations

from copy import deepcopy
from typing import Any

from post_rag.models import Item, ShipmentSlots, SlotOperation, SlotUpdate


def apply_updates(slots: ShipmentSlots, updates: list[SlotUpdate]) -> tuple[ShipmentSlots, list[str]]:
    result = slots.model_copy(deep=True)
    changed: list[str] = []

    for update in updates:
        if update.operation == SlotOperation.KEEP:
            continue

        if update.field == "items":
            current = list(result.items)
            values = [Item.model_validate(item) for item in (update.value or [])]
            if update.operation == SlotOperation.REPLACE:
                result.items = values
            elif update.operation == SlotOperation.ADD:
                known = {item.normalized_name for item in current}
                result.items = current + [item for item in values if item.normalized_name not in known]
            elif update.operation == SlotOperation.REMOVE:
                removed = {item.normalized_name for item in values}
                result.items = [item for item in current if item.normalized_name not in removed]
            elif update.operation == SlotOperation.CLEAR:
                result.items = []
        else:
            attr = "destination_code" if update.field == "destination" else update.field
            value = None if update.operation == SlotOperation.CLEAR else deepcopy(update.value)
            setattr(result, attr, value)

        changed.append(update.field)

    return result, list(dict.fromkeys(changed))


# 품목 판정 캐시
#
# LLM 판정만 재사용한다. 국가 조건 조회와 요금 계산은 결정적인 코드라 매 턴 다시 실행한다.
# 캐시 키에 판정 결과를 바꾸는 입력(국가, 서비스, 품목)을 모두 넣어, 국가나 서비스가 바뀌면
# 키가 달라져 자동으로 다시 판정된다. 변경 필드별 무효화 규칙을 따로 관리하지 않는다.

CACHEABLE_STATUSES = {"prohibited", "restricted", "no_restriction_found", "conflicting"}


def decision_cache_key(destination_code: str | None, service: str | None, item: Item) -> str:
    return f"{destination_code or ''}|{service or ''}|{item.normalized_name}"


def relabel_evidence(
    decision: dict[str, Any], evidence: list[dict[str, Any]], item_index: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """캐시된 판정의 근거 ID를 현재 품목 순서(I{n}E{m})로 다시 매긴다.

    품목을 빼거나 추가하면 순서가 바뀌므로, 이전 ID를 그대로 쓰면 다른 품목의 근거 ID와 겹친다.
    """
    mapping: dict[str, str] = {}
    relabeled: list[dict[str, Any]] = []
    for evidence_index, entry in enumerate(evidence, 1):
        new_id = f"I{item_index}E{evidence_index}"
        mapping[str(entry["evidence_id"])] = new_id
        relabeled.append({**entry, "evidence_id": new_id})
    new_decision = deepcopy(decision)
    for quote in new_decision.get("evidence", []):
        quote["evidence_id"] = mapping.get(quote["evidence_id"], quote["evidence_id"])
    return new_decision, relabeled
