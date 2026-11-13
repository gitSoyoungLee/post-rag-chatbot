from post_rag.models import Item, ShipmentSlots, SlotOperation, SlotUpdate
from post_rag.state import apply_updates, invalidated_results


def test_follow_up_keeps_items_and_replaces_destination() -> None:
    initial = ShipmentSlots(
        destination_code="US",
        items=[Item(original_name="립밤", normalized_name="립밤", categories=["화장품"])],
        actual_weight_g=1500,
    )
    updates = [
        SlotUpdate(field="destination", operation=SlotOperation.REPLACE, value="JP"),
        SlotUpdate(field="items", operation=SlotOperation.KEEP),
    ]

    updated, changed = apply_updates(initial, updates)

    assert updated.destination_code == "JP"
    assert updated.items[0].normalized_name == "립밤"
    assert updated.actual_weight_g == 1500
    assert invalidated_results(changed) == {"country_conditions", "item_decisions", "rate_result"}


def test_add_and_remove_items() -> None:
    initial = ShipmentSlots(
        items=[Item(original_name="립밤", normalized_name="립밤", categories=["화장품"])]
    )
    add = SlotUpdate(
        field="items",
        operation=SlotOperation.ADD,
        value=[{"original_name": "스티커", "normalized_name": "스티커", "categories": ["문구류"]}],
    )
    remove = SlotUpdate(
        field="items",
        operation=SlotOperation.REMOVE,
        value=[{"original_name": "립밤", "normalized_name": "립밤", "categories": ["화장품"]}],
    )

    updated, changed = apply_updates(initial, [add, remove])

    assert [item.normalized_name for item in updated.items] == ["스티커"]
    assert changed == ["items"]
