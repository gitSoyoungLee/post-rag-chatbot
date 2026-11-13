from post_rag.validation import validate_answer


PAYLOAD = {
    "slots": {"actual_weight_g": 1500},
    "rate_result": {"amount_krw": 57000, "bracket_kg": 1.5},
    "evidence": {
        "립밤": [
            {
                "evidence_id": "I1E1",
                "content": "EMS 제한중량은 30kg이며 화장품은 확인이 필요합니다.",
            }
        ]
    },
}


def test_answer_validation_accepts_input_calculation_and_evidence_numbers() -> None:
    answer = "입력 중량은 1.5kg이고 예상 기본요금은 57,000원입니다. 최대 30kg입니다. [I1E1]"

    assert validate_answer(answer, PAYLOAD) == []


def test_answer_validation_rejects_unknown_citation_and_number() -> None:
    answer = "예상 기본요금은 99,000원입니다. [I9E9]"

    assert validate_answer(answer, PAYLOAD) == [
        "존재하지 않는 인용: I9E9",
        "출처 없는 수치: 99000원",
    ]
