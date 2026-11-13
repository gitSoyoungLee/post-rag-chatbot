from post_rag.models import Item, ShipmentSlots, SlotOperation, SlotUpdate
from post_rag.state import apply_updates, decision_cache_key, relabel_evidence


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
    assert changed == ["destination"]


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


def test_cache_key_changes_with_country_and_service() -> None:
    item = Item(original_name="립밤", normalized_name="립밤", categories=["화장품"])
    keys = {
        decision_cache_key("US", "ems", item),
        decision_cache_key("JP", "ems", item),
        decision_cache_key("US", "parcel", item),
        decision_cache_key("US", None, item),
    }
    assert len(keys) == 4


def test_relabel_evidence_rewrites_quote_ids() -> None:
    decision = {"item": "과자", "evidence": [{"evidence_id": "I2E1", "quote": "음식물"}]}
    evidence = [{"evidence_id": "I2E1", "content": "음식물"}, {"evidence_id": "I2E2", "content": "기타"}]

    new_decision, new_evidence = relabel_evidence(decision, evidence, item_index=1)

    assert [entry["evidence_id"] for entry in new_evidence] == ["I1E1", "I1E2"]
    assert new_decision["evidence"][0]["evidence_id"] == "I1E1"
    assert decision["evidence"][0]["evidence_id"] == "I2E1"  # 원본 캐시는 변경하지 않음
