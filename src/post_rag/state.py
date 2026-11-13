from __future__ import annotations

from copy import deepcopy

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


def invalidated_results(changed_fields: list[str]) -> set[str]:
    invalidated: set[str] = set()
    fields = set(changed_fields)
    if "destination" in fields:
        invalidated.update({"country_conditions", "item_decisions", "rate_result"})
    if "items" in fields:
        invalidated.add("item_decisions")
    if fields & {"actual_weight_g", "dimensions_cm"}:
        invalidated.add("rate_result")
    if "preferred_service" in fields:
        invalidated.update({"country_conditions", "item_decisions", "rate_result"})
    return invalidated

