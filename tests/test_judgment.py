from post_rag.judgment import validate_decision
from post_rag.models import Evidence, EvidenceQuote, ItemDecision, ItemStatus


EVIDENCE = [
    Evidence(
        evidence_id="E1",
        document_id="country-US",
        title="미국 발송조건",
        content="금지·제한품목\n화장품은 통관 확인이 필요합니다.",
        country_code="US",
        service_type="ems",
        source_type="우체국안내",
    )
]


def test_decision_quote_must_exist_in_evidence() -> None:
    valid = ItemDecision(
        item="립밤",
        status=ItemStatus.RESTRICTED,
        reason="화장품 통관 확인이 필요함",
        evidence=[EvidenceQuote(evidence_id="E1", quote="화장품은 통관 확인이 필요합니다.")],
    )
    invalid = valid.model_copy(
        update={"evidence": [EvidenceQuote(evidence_id="E1", quote="립밤은 발송할 수 없습니다.")]}
    )

    assert validate_decision(valid, EVIDENCE) == []
    assert validate_decision(invalid, EVIDENCE) == ["근거에 없는 인용문: E1"]


def test_restricted_decision_requires_quote() -> None:
    decision = ItemDecision(
        item="립밤",
        status=ItemStatus.RESTRICTED,
        reason="제한",
    )

    assert validate_decision(decision, EVIDENCE) == ["판정에 필요한 인용문이 없음"]
