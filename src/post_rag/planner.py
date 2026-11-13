from __future__ import annotations

from post_rag.models import OperationPlan, RequestAnalysis, RequestedOutput, ShipmentSlots


def plan_operations(analysis: RequestAnalysis, slots: ShipmentSlots) -> OperationPlan:
    requested = set(analysis.requested_outputs)
    operations: list[str] = []
    missing: list[str] = []

    if RequestedOutput.AVAILABLE_SERVICES in requested:
        if not slots.destination_code:
            missing.append("destination")
        else:
            operations.append("lookup_conditions")

    if RequestedOutput.ITEM_POLICY in requested:
        if not slots.destination_code:
            missing.append("destination")
        if not slots.items:
            missing.append("items")
        if slots.destination_code and slots.items:
            operations.extend(["retrieve_by_item", "judge_items"])

    if RequestedOutput.EMS_RATE in requested:
        if not slots.destination_code:
            missing.append("destination")
        if slots.actual_weight_g is None:
            missing.append("actual_weight_g")
        if slots.destination_code and slots.actual_weight_g is not None:
            operations.extend(["lookup_conditions", "calculate_ems_rate"])

    if RequestedOutput.GENERAL_ANSWER in requested:
        operations.append("retrieve_general_regulations")

    return OperationPlan(
        operations=list(dict.fromkeys(operations)),
        missing_fields=list(dict.fromkeys(missing)),
    )

