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


TABLE_EVIDENCE = [
    Evidence(
        evidence_id="E1",
        document_id="common-items",
        title="보낼 수 없는 물품",
        content="| **리튬 이온·리튬 메탈 등의 배터리** | **불가** | 종류, 용량에 상관없이 발송 불가 |",
        country_code="ALL",
        service_type="ALL",
        source_type="우체국안내",
    )
]


def _prohibited(quote: str) -> ItemDecision:
    return ItemDecision(
        item="노트북",
        status=ItemStatus.PROHIBITED,
        reason="리튬 배터리",
        evidence=[EvidenceQuote(evidence_id="E1", quote=quote)],
    )


def test_quote_ignores_markdown_table_markup() -> None:
    assert validate_decision(_prohibited("리튬 이온·리튬 메탈 등의 배터리 불가"), TABLE_EVIDENCE) == []


def test_quote_with_ellipsis_requires_every_fragment() -> None:
    assert validate_decision(_prohibited("리튬 이온... 용량에 상관없이 발송 불가"), TABLE_EVIDENCE) == []
    # 조각 하나라도 원문에 없으면 실패
    assert validate_decision(_prohibited("리튬 이온... 신고하면 발송 가능"), TABLE_EVIDENCE) == [
        "근거에 없는 인용문: E1"
    ]


def test_quote_may_include_evidence_title() -> None:
    assert validate_decision(_prohibited("보낼 수 없는 물품 리튬 이온"), TABLE_EVIDENCE) == []


SOURCE_WITH_BULLETS = [
    Evidence(
        evidence_id="E1",
        document_id="country-SG",
        title="싱가포르 발송조건",
        content="- 김치 접수 가능\n- 용기는 금속 재질의 포장 용기(캔)로 한정\n(식육가공품) : 소고기가 포함된 카레 \\* 예시",
        country_code="SG",
        service_type="ems",
        source_type="우체국안내",
    )
]


def test_quote_ignores_bullets_spacing_and_escapes() -> None:
    for quote in ("김치 접수 가능 용기는 금속 재질의", "(식육가공품): 소고기가 포함된 카레 예시"):
        assert validate_decision(_prohibited(quote), SOURCE_WITH_BULLETS) == []


def test_skipped_text_without_ellipsis_is_rejected() -> None:
    # 중간 내용을 생략 표시 없이 건너뛴 인용은 원문에 없는 연속 구절이다
    assert validate_decision(_prohibited("김치 접수 가능 포장 용기(캔)로 한정"), SOURCE_WITH_BULLETS) == [
        "근거에 없는 인용문: E1"
    ]
    assert validate_decision(_prohibited("김치 접수 가능 [...] 포장 용기(캔)로 한정"), SOURCE_WITH_BULLETS) == []
