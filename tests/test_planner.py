from post_rag.models import (
    Item,
    QueryType,
    RequestAnalysis,
    RequestedOutput,
    ShipmentSlots,
)
from post_rag.planner import plan_operations


def test_planner_runs_only_requested_operations() -> None:
    slots = ShipmentSlots(
        destination_code="US",
        items=[Item(original_name="립밤", normalized_name="립밤", categories=["화장품"])],
        actual_weight_g=1500,
    )
    analysis = RequestAnalysis(
        query_type=QueryType.SHIPMENT_REQUEST,
        requested_outputs=[RequestedOutput.ITEM_POLICY],
    )

    plan = plan_operations(analysis, slots)

    assert plan.operations == ["retrieve_by_item", "judge_items"]
    assert "lookup_conditions" not in plan.operations
    assert "calculate_ems_rate" not in plan.operations


def test_planner_reports_missing_rate_input() -> None:
    analysis = RequestAnalysis(
        query_type=QueryType.SHIPMENT_REQUEST,
        requested_outputs=[RequestedOutput.EMS_RATE],
    )

    plan = plan_operations(analysis, ShipmentSlots(destination_code="JP"))

    assert plan.operations == []
    assert plan.missing_fields == ["actual_weight_g"]

